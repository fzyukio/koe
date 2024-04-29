import { postRequest } from "./ajax-handler";

const KOE = 1;
const USER = 2;

const nameMap = {
  [KOE]: "Koe",
  [USER]: "You",
};

let webSockets = {};

const getWsConnection = function (token) {
  let webSocket = webSockets[token];
  if (
    webSocket !== undefined &&
    (webSocket.readyState === WebSocket.CLOSING ||
      webSocket.readyState === WebSocket.CLOSING)
  ) {
    delete webSockets[token];
    webSocket = undefined;
  }

  if (webSocket === undefined) {
    let tokens = Object.keys(webSockets);
    if (tokens.length > 0) {
      for (let i = 0; i < tokens.length; i++) {
        let t = tokens[i];
        webSockets[t].close();
        delete webSockets[t];
      }
    }

    return new Promise(function (resolve, reject) {
      // ws = new WebSocket("wss://go-llama-proxy.io.ac.nz/");
      const ws = new WebSocket(window.appCache.consts.CHAT_SERVER_URL);
      webSockets[token] = ws;
      ws.onopen = function () {
        console.log("Websocket opened");
        ws.send(
          JSON.stringify({
            type: "authenticate",
            message: token,
          })
        );
      };
      ws.onmessage = function (response) {
        if (response.data === "ok") {
          resolve(ws);
        } else {
          reject(new Error("not an ok response"));
        }
      };
      ws.onerror = function () {
        console.log("Websocket error");
        ws.close();
        reject(new Error("Websocket error"));
      };

      ws.onclose = function () {
        delete webSockets[token];
      };
    });
  } else {
    return new Promise(function (resolve) {
      if (webSocket.readyState === WebSocket.OPEN) {
        resolve(webSocket);
      } else {
        webSocket.onopen = function () {
          resolve(webSocket);
        };
      }
    });
  }
};

const sendWsMessage = function (webSocket, message) {
  let messageBox = $("#message-box");
  let messageEl = renderOneMessage(nameMap[KOE], "...");
  messageBox.append(messageEl);
  let messageBody = messageEl.find(".message-body");
  let fullMsg = "";

  return new Promise(function (resolve) {
    webSocket.onmessage = function (response) {
      let chunk = response.data;
      if (chunk === "<start>") {
        messageBody.html("");
      } else if (chunk === "<end>") {
        resolve(fullMsg);
      } else {
        fullMsg += chunk;
        messageBody.html(fullMsg);
      }
    };

    webSocket.send(
      JSON.stringify({
        type: "question",
        message,
      })
    );
  });
};

const isTokenExpired = function (token) {
  const base64Url = token.split(".")[1];
  const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
  const jsonPayload = decodeURIComponent(
    atob(base64)
      .split("")
      .map(function (c) {
        return "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2);
      })
      .join("")
  );

  const { exp } = JSON.parse(jsonPayload);
  const expired = Date.now() >= exp * 1000;
  return expired;
};

const getChatHistory = function () {
  let historyList = localStorage.getItem("chatHistory");
  if (historyList === null) {
    historyList = [
      {
        from: KOE,
        msg: "Hi there, how can I help you today?",
      },
    ];
  } else {
    historyList = JSON.parse(historyList);
  }

  return historyList;
};

const addChatHistory = function (chatHistory, from, msg) {
  chatHistory.push({
    from,
    msg,
  });

  localStorage.setItem("chatHistory", JSON.stringify(chatHistory));
  renderChatHistory(chatHistory);
};

const getToken = function () {
  return new Promise(function (resolve) {
    let currentToken = localStorage.getItem("chat-token");
    if (currentToken !== null) {
      if (isTokenExpired(currentToken)) {
        currentToken = null;
      }
    }

    if (currentToken) {
      resolve(currentToken);
      return;
    }

    postRequest({
      requestSlug: "koe/get-token",
      onSuccess(token) {
        localStorage.setItem("chat-token", token);
        resolve(token);
      },
    });
  });
};

export const initChat = function () {
  const _chatHistory = getChatHistory();

  const dialogModal = $("#chat-modal");
  $("#chat-open-button").on("click", () => {
    dialogModal.modal("show");
  });
  // const chatButtonWrapper = $("#chat-button-wrapper");
  // if (chatButtonWrapper.length == 0) {
  //     return
  // }

  // const userName = chatButtonWrapper.attr("data-username");
  // const email = chatButtonWrapper.attr("data-email");
  // const koeAvatar = chatButtonWrapper.attr("data-koe-avatar");
  // ReactDOM.render(<ChatButton userName={userName} email={email} koeAvatar={koeAvatar}/>, document.getElementById('chat-button-wrapper'));

  initChatSubmitButton(_chatHistory);
};

// Function to get caret position in text area
let getCaretPosition = function (textarea) {
  let caretPos = 0;
  if (document.selection) {
    textarea.focus();
    let sel = document.selection.createRange();
    sel.moveStart("character", -textarea.value.length);
    caretPos = sel.text.length;
  } else if (textarea.selectionStart || textarea.selectionStart == "0") {
    caretPos = textarea.selectionStart;
  }
  return caretPos;
};

const renderOneMessage = function (name, msg) {
  return $(`
        <div class="message">
            <div class="message-name">${name}:</div>
            <div class="message-body">${msg}</div>
        </div>
    `);
};

const renderChatHistory = function (chatHistory) {
  let messageBox = $("#message-box");
  messageBox.html("");
  $.each(chatHistory, function (_, chat) {
    let name = nameMap[chat.from];
    let messageEl = renderOneMessage(name, chat.msg);
    messageBox.append(messageEl);
  });
};

const initChatSubmitButton = function (_chatHistory) {
  let submitButton = $("#send-message");
  if (submitButton.length === 0) {
    return;
  }
  let messageTextArea = $("#chat-message");
  let shiftPressed = false;

  function toggleButton() {
    let text = messageTextArea.val();
    let messageLength = text.length;
    if (messageLength > 0) {
      submitButton.prop("disabled", false);
    } else {
      submitButton.prop("disabled", true);
    }
  }

  // Handle key press events
  messageTextArea.keydown(function (e) {
    // Check for ENTER key
    if (e.keyCode === 13) {
      // Prevent default behavior of ENTER
      e.preventDefault();
      // Check if SHIFT key is pressed

      shiftPressed = shiftPressed || e.shiftKey;

      if (shiftPressed) {
        // Add a new line
        let content = this.value;
        let caret = getCaretPosition(this);
        this.value =
          content.substring(0, caret) + "\n" + content.substring(caret);
        e.stopPropagation();
      } else {
        // Trigger button click event
        submitButton.click();
      }
    }
  });

  // Handle button click event
  submitButton.click(function () {
    let message = messageTextArea.val();
    // Disable text area
    messageTextArea.val("");
    addChatHistory(_chatHistory, USER, message);
    toggleButton();
    messageTextArea.prop("disabled", true);

    getToken()
      .then(function (token) {
        return getWsConnection(token);
      })
      .then(function (ws) {
        return sendWsMessage(ws, message);
      })
      .then(function (response) {
        addChatHistory(_chatHistory, KOE, response);
      });

    getToken().then(function (token) {
      console.log(`Token = ${token}`);
      messageTextArea.prop("disabled", false);
      // Auto focus on text area
      messageTextArea.focus();
      // Enable button
      messageTextArea.prop("disabled", false);
    });
  });

  messageTextArea.on("input", function () {
    toggleButton();
  });

  toggleButton();
  renderChatHistory(_chatHistory);
};
