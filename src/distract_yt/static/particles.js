/* Interactive particle / points background.
   A field of pastel dots that pulse and grow as the cursor approaches.
   The canvas is a fixed, click-through layer behind the whole app (see CSS). */

(function () {
  "use strict";

  var canvas = document.getElementById("bg-canvas");
  if (!canvas) return;

  var ctx = canvas.getContext("2d");
  var width = window.innerWidth;
  var height = window.innerHeight;
  var dots = [];
  var mousePos = { x: -20, y: -20 };
  // Pastel palette so the faint dots sit nicely over the dark neon theme.
  var colors = ["#a8e6cf", "#dcedc1", "#ffd3b6", "#ffaaa5", "#ff8b94"];

  function d2(p1, p2) {
    var xs = p2.x - p1.x;
    xs *= xs;
    var ys = p2.y - p1.y;
    ys *= ys;
    return Math.sqrt(xs + ys);
  }

  function Dot(x, y, color) {
    var self = this;
    this.x = x;
    this.y = y;
    this.targetRadius = 3;
    this.radius = 3;
    this.color = color;

    this.draw = function () {
      var d = d2(self, mousePos);
      self.targetRadius = d < 100 ? 3 + (100 - d) / 7 : 3;
      self.radius += (self.targetRadius - self.radius) * 0.1;
      ctx.beginPath();
      ctx.arc(self.x, self.y, self.radius, 0, 2 * Math.PI, false);
      ctx.fillStyle = self.color;
      ctx.fill();
    };
  }

  function placeDots(step) {
    dots = [];
    var ci = 0;
    for (var x = 14; x < width; x += step) {
      for (var y = 14; y < height; y += step) {
        dots.push(new Dot(x, y, colors[ci % colors.length]));
        ci++;
      }
    }
  }

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
    // coarser grid on wide screens keeps density pleasant & fast
    placeDots(width < 700 ? 16 : 44);
  }

  function loop() {
    ctx.clearRect(0, 0, width, height);
    for (var i = 0; i < dots.length; i++) dots[i].draw();
    requestAnimationFrame(loop);
  }

  // Track the cursor on the window (the canvas has pointer-events: none so it
  // never blocks clicks, and touchmove is passive so page scrolling is intact).
  window.addEventListener("mousemove", function (e) {
    mousePos.x = e.pageX;
    mousePos.y = e.pageY;
  });
  window.addEventListener("touchstart", function (e) {
    var t = e.touches && e.touches[0];
    if (t) { mousePos.x = t.pageX; mousePos.y = t.pageY; }
  }, { passive: true });
  window.addEventListener("touchmove", function (e) {
    var t = e.touches && e.touches[0];
    if (t) { mousePos.x = t.pageX; mousePos.y = t.pageY; }
  }, { passive: true });
  window.addEventListener("resize", resize);

  resize();
  loop();
})();