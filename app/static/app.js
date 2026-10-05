// Live character counter for the paper text field. Progressive enhancement only:
// the page works without it, and tests do not depend on it.
(function () {
  var text = document.getElementById("text");
  var counter = document.getElementById("char-count");
  if (!text || !counter) return;
  var min = parseInt(counter.getAttribute("data-min"), 10) || 0;
  function update() {
    var n = text.value.length;
    counter.textContent = n + (n < min ? " / " + min + " characters minimum" : " characters");
  }
  text.addEventListener("input", update);
  update();
})();
