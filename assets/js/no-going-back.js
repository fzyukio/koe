/**
 * Include this file will disable the back button. Which is nice when browsing by touch pad.
 * Too often swiping to the left is mistaken as going back.
 */
(function (global) {
  if (typeof global === "undefined") {
    throw new Error("window is undefined");
  }

  let _hash = "!";
  let noBackPlease = function () {
    global.location.href += "#";

    // making sure we have the fruit available for juice (^__^)
    global.setTimeout(function () {
      global.location.href += "!";
    }, 50);
  };

  global.onhashchange = function () {
    if (global.location.hash !== _hash) {
      global.location.hash = _hash;
    }
  };

  global.onload = function () {
    noBackPlease();
  };
}(window));
