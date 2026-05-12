// Footer date
(function () {
  const el = document.getElementById("footer-date");
  if (el) {
    el.textContent = new Date()
      .toLocaleDateString("en-US", { year: "numeric", month: "long" })
      .toUpperCase();
  }
})();

// Auto-dismiss flash messages after 5s
(function () {
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach((f) => {
    setTimeout(() => f.remove(), 5000);
  });
})();

// File input: show selected filename
(function () {
  const input = document.getElementById("file");
  const display = document.getElementById("file-name-display");
  if (input && display) {
    input.addEventListener("change", () => {
      display.textContent = input.files[0] ? input.files[0].name : "";
    });
  }
})();

// Jobs: trigger job via AJAX
function triggerJob(jobId, name) {
  const btn = document.getElementById("trigger-btn-" + jobId);
  const badge = document.getElementById("status-badge-" + jobId);

  btn.disabled = true;
  btn.textContent = "Running…";
  if (badge) {
    badge.className = "badge badge--running";
    badge.innerHTML = '<span class="badge-dot"></span>running';
  }

  fetch("/jobs/" + jobId + "/trigger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        btn.textContent = "▶ Run";
        btn.disabled = false;
        // Refresh the page after a short delay so the status reflects DB update
        setTimeout(() => window.location.reload(), 2500);
      } else {
        btn.textContent = "▶ Run";
        btn.disabled = false;
        alert("Error: " + (data.error || "Unknown error"));
        if (badge) {
          badge.className = "badge badge--failed";
          badge.innerHTML = '<span class="badge-dot"></span>failed';
        }
      }
    })
    .catch(() => {
      btn.textContent = "▶ Run";
      btn.disabled = false;
      alert("Network error triggering job.");
    });
}
