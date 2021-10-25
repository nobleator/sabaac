(function() {
    var typingTimer;
    var doneTypingInterval = 250;
    var gameCode = document.getElementById("gamecodeDiv").innerText;
    var usernameInput = document.getElementById("username");
    var startgameButton = document.getElementById("startgame");
    var ws;
    
    document.onreadystatechange = function () {
        if (document.readyState == "complete") {
            ws = new WebSocket("ws://" + window.location.host + "/lobbyws")
            ws.onopen = function() {
                console.log("WebSocket connection opened");
                doneTyping();
            }
            ws.onmessage = function(evt) {
                if (evt.data == "") {
                    return;
                }
                var incomingGameData = JSON.parse(JSON.parse(evt.data));
                if (incomingGameData.startgame === true) {
                    window.location.href = "/sabaac/" + gameCode;
                } else {
                    var listOfPlayers = "";
                    if (incomingGameData.players != null) {
                        incomingGameData.players.forEach(function(player) {
                            listOfPlayers += "<div>Player " + player.turnorder + ": " + player.username + "</div>"
                        });
                    }
                    document.getElementById("listOfPlayers").innerHTML = listOfPlayers;
                }
            }
            ws.onclose = function() {
                console.log("Connection closed");
            }
        }
    }
    
    usernameInput.addEventListener("keyup", function() {
        clearTimeout(typingTimer);
        if (usernameInput.value) {
            typingTimer = setTimeout(doneTyping, doneTypingInterval);
        }
    });
    
    startgameButton.addEventListener("click", function(event) {
        event.preventDefault();
        ws.send(JSON.stringify({"code": gameCode, "username": usernameInput.value, "startgame": true}));
        window.location.href = "/sabaac/" + gameCode;
    });
    
    function doneTyping() {
        ws.send(JSON.stringify({"code": gameCode, "username": usernameInput.value, "startgame": false}));
    }
    
    window.onbeforeunload = function() {
        sessionStorage.setItem("username", usernameInput.value);
    }
    
    window.onload = function() {
        var name = sessionStorage.getItem("username");
        if (name != null) {
            usernameInput.value = name;
        }
    }
})();
