function logAction(action, actionValue=null) {
    console.log("Sending message");
    ws.send(JSON.stringify({"code": gameCode, "action": action, "actionValue": actionValue}));
}

if (Object.freeze) {
    var actionEnums = Object.freeze({"DRAW_DECK": 1, "DRAW_DISCARD": 2, "PASS": 3, "DISCARD": 4});
} else {
    var actionEnums = {"DRAW_DECK": 1, "DRAW_DISCARD": 2, "PASS": 3, "DISCARD": 4};
}
var gameCode = document.getElementById("gamecodeDiv").innerText;
var ws;

document.onreadystatechange = function () {
    if (document.readyState == "complete") {
        document.getElementById("deck").onclick = function() {
            logAction(actionEnums.DRAW_DECK);
        };
        document.getElementById("discardPile").onclick = function() {
            logAction(actionEnums.DRAW_DISCARD);
        };
        document.getElementById("pass").onclick = function() {
            logAction(actionEnums.PASS);
        };

        ws = new WebSocket("ws://" + window.location.host + "/sabaacws")
        ws.onopen = function() {
            console.log("WebSocket connection opened");
        }
        ws.onmessage = function(evt) {
            console.log("Receiving message");
            if (evt.data == "") {
                return;
            }
            // TODO: Double encoding?
            var incomingGameData = JSON.parse(JSON.parse(evt.data));
            console.log(incomingGameData);

            if (incomingGameData.topdiscard && incomingGameData.topdiscard !== null) {
                var discard = incomingGameData.topdiscard;
                document.getElementById("discardPile").innerHTML = discard.rank + " of " + discard.suite;
            }
            document.getElementById("currentPlayer").innerHTML = incomingGameData.currentplayer;
            document.getElementById("userCredits").innerHTML = incomingGameData.playercredits;
            document.getElementById("sabaacPot").innerHTML = incomingGameData.sabaacpot;
            document.getElementById("handPot").innerHTML = incomingGameData.handpot;
            
            var playerHand =  incomingGameData.playerhand;
            var handOutput = "";
            playerHand.forEach(function(elem) {
                handOutput += "<button type='button' class='card' onclick='logAction(&quot;" + actionEnums.DISCARD + "&quot;, " + elem.id + ")'>" + elem.rank + " of " + elem.suite + "</button>"
            });
            document.getElementById("playerHand").innerHTML = handOutput;

            var messages = incomingGameData.messages;
            var messageOutput = "";
            messages.forEach(function(elem) {
                var convertedDate = new Date(elem.timestamp).toLocaleTimeString();
                messageOutput = "<span class='message'>" + elem.body + " at: <span title='" + convertedDate + "'>" + convertedDate + "</span></span>" + messageOutput;
            });

            document.getElementById("messageLog").innerHTML = messageOutput;
            if (incomingGameData.winner !== null) {
                document.getElementById("winner").innerHTML = incomingGameData.winner.username;
                document.getElementById("end-of-game-modal").style.visibility = "visible";
            } else {
                document.getElementById("round").innerHTML = incomingGameData.round;
            }
        }
        ws.onclose = function() {
            console.log("Connection closed");
        }
    }
}
