/**
 * Art Movements Watch Collection - Shared Clock Logic
 * ===================================================
 *
 * Real-time clock engine with smooth and tick modes.
 * Uses requestAnimationFrame for 60fps performance.
 */

class ArtWatch {
  constructor(container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;

    if (!this.container) {
      console.error('Watch container not found');
      return;
    }

    this.options = {
      smooth: true,           // Smooth sweeping seconds vs ticking
      timezone: null,         // Optional timezone offset (hours)
      speedMultiplier: 1,     // For demo/testing
      onUpdate: null,         // Callback on each update
      ...options
    };

    this.hourHand = this.container.querySelector('.hour-hand');
    this.minuteHand = this.container.querySelector('.minute-hand');
    this.secondHand = this.container.querySelector('.second-hand');
    this.digitalDisplay = this.container.querySelector('.digital-time');

    this.running = false;
    this.lastSecond = -1;

    this.init();
  }

  init() {
    // Add smooth/tick class for CSS transitions
    this.container.classList.toggle('smooth-seconds', this.options.smooth);
    this.container.classList.toggle('tick-seconds', !this.options.smooth);

    this.start();
  }

  getTime() {
    const now = new Date();

    if (this.options.timezone !== null) {
      const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
      return new Date(utc + (3600000 * this.options.timezone));
    }

    return now;
  }

  calculateAngles(time) {
    const hours = time.getHours() % 12;
    const minutes = time.getMinutes();
    const seconds = time.getSeconds();
    const ms = time.getMilliseconds();

    // Calculate precise angles
    let secondAngle, minuteAngle, hourAngle;

    if (this.options.smooth) {
      // Smooth: include milliseconds for fluid motion
      secondAngle = ((seconds + ms / 1000) / 60) * 360;
      minuteAngle = ((minutes + seconds / 60) / 60) * 360;
      hourAngle = ((hours + minutes / 60 + seconds / 3600) / 12) * 360;
    } else {
      // Tick: snap to whole seconds
      secondAngle = (seconds / 60) * 360;
      minuteAngle = ((minutes + seconds / 60) / 60) * 360;
      hourAngle = ((hours + minutes / 60) / 12) * 360;
    }

    return { hourAngle, minuteAngle, secondAngle, hours, minutes, seconds };
  }

  update() {
    if (!this.running) return;

    const time = this.getTime();
    const angles = this.calculateAngles(time);

    // Update analog hands
    if (this.hourHand) {
      this.hourHand.style.transform = `rotate(${angles.hourAngle}deg)`;
    }
    if (this.minuteHand) {
      this.minuteHand.style.transform = `rotate(${angles.minuteAngle}deg)`;
    }
    if (this.secondHand) {
      this.secondHand.style.transform = `rotate(${angles.secondAngle}deg)`;
    }

    // Update digital display if present
    if (this.digitalDisplay) {
      const h = String(time.getHours()).padStart(2, '0');
      const m = String(time.getMinutes()).padStart(2, '0');
      const s = String(time.getSeconds()).padStart(2, '0');
      this.digitalDisplay.textContent = `${h}:${m}:${s}`;
    }

    // Callback
    if (this.options.onUpdate && angles.seconds !== this.lastSecond) {
      this.options.onUpdate(time, angles);
      this.lastSecond = angles.seconds;
    }

    requestAnimationFrame(() => this.update());
  }

  start() {
    this.running = true;
    this.update();
  }

  stop() {
    this.running = false;
  }

  setSmooth(smooth) {
    this.options.smooth = smooth;
    this.container.classList.toggle('smooth-seconds', smooth);
    this.container.classList.toggle('tick-seconds', !smooth);
  }
}

/**
 * Initialize all watches on a page
 */
function initAllWatches(options = {}) {
  const watches = document.querySelectorAll('.watch-face');
  return Array.from(watches).map(watch => new ArtWatch(watch, options));
}

/**
 * Generate hour indices HTML
 */
function generateIndices(count = 12, className = 'index') {
  let html = '<div class="indices">';
  for (let i = 0; i < count; i++) {
    html += `<div class="${className}"></div>`;
  }
  html += '</div>';
  return html;
}

/**
 * Generate minute markers HTML
 */
function generateMinuteMarkers(className = 'minute-marker') {
  let html = '<div class="minute-markers">';
  for (let i = 0; i < 60; i++) {
    const isHour = i % 5 === 0;
    html += `<div class="${className}${isHour ? ' hour-marker' : ''}" style="transform: rotate(${i * 6}deg)"></div>`;
  }
  html += '</div>';
  return html;
}

/**
 * Format time for accessibility
 */
function formatTimeForSR(date) {
  const hours = date.getHours();
  const minutes = date.getMinutes();
  const period = hours >= 12 ? 'PM' : 'AM';
  const h = hours % 12 || 12;
  return `${h}:${String(minutes).padStart(2, '0')} ${period}`;
}

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { ArtWatch, initAllWatches, generateIndices, generateMinuteMarkers };
}
