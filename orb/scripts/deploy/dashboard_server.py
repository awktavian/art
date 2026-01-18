#!/usr/bin/env python3
"""Live Dashboard Server - Serves real-time training metrics."""

import http.server
import socketserver
import json
import re
from pathlib import Path

PORT = 8889


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            # Serve training metrics as JSON
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            metrics = self.get_training_metrics()
            self.wfile.write(json.dumps(metrics).encode())

        elif self.path == "/" or self.path == "/dashboard":
            # Serve dashboard HTML
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            html = self.get_dashboard_html()
            self.wfile.write(html.encode())
        else:
            super().do_GET()

    def get_training_metrics(self):
        """Parse training log and return metrics."""
        log_file = Path("logs/real_convergence.log")

        if not log_file.exists():
            return {"status": "waiting", "epochs": [], "losses": []}

        try:
            log_text = log_file.read_text()

            # Parse epochs and losses
            matches = re.findall(r"Epoch (\d+) - Avg Loss: ([\d.]+)", log_text)
            epochs = [int(m[0]) for m in matches]
            losses = [float(m[1]) for m in matches]

            # Parse convergence info
            convergence_matches = re.findall(r"Avg change \(last 4\): ([\d.]+)", log_text)
            avg_change = float(convergence_matches[-1]) if convergence_matches else None

            # Check if converged
            converged_match = re.search(r"CONVERGED after (\d+) epochs", log_text)
            converged = converged_match is not None

            return {
                "status": "converged" if converged else "training",
                "epochs": epochs,
                "losses": losses,
                "avg_change": avg_change,
                "converged": converged,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_dashboard_html(self):
        """Generate dashboard HTML."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Omnimodel Training Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #000; color: #0f0; margin: 0; padding: 20px; }
        h1 { text-align: center; color: #0ff; }
        .status { text-align: center; font-size: 24px; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }
        .stat { background: #111; border: 2px solid #0f0; border-radius: 10px; padding: 20px; text-align: center; }
        .stat-value { font-size: 36px; color: #0ff; font-weight: bold; }
        .stat-label { font-size: 14px; color: #0f0; margin-top: 5px; }
        .chart { background: #111; border: 2px solid #0f0; border-radius: 10px; padding: 20px; }
    </style>
</head>
<body>
    <h1>🚀 OMNIMODEL TRAINING - M3 ULTRA 512GB</h1>
    <div class="status" id="status">● TRAINING IN PROGRESS</div>
    <div class="stats" id="stats"></div>
    <div class="chart" id="chart"></div>

    <script>
        async function update() {
            try {
                const res = await fetch('/metrics');
                const data = await res.json();

                if (data.status === 'waiting') {
                    document.getElementById('stats').innerHTML = '<div class="stat"><div class="stat-value">Initializing...</div></div>';
                    return;
                }

                const epochs = data.epochs || [];
                const losses = data.losses || [];

                if (losses.length === 0) return;

                // Update stats
                const improvement = ((losses[0] - losses[losses.length-1]) / losses[0] * 100).toFixed(1);
                document.getElementById('stats').innerHTML = `
                    <div class="stat"><div class="stat-value">${epochs[epochs.length-1]}/100</div><div class="stat-label">Epochs</div></div>
                    <div class="stat"><div class="stat-value">${losses[losses.length-1].toFixed(4)}</div><div class="stat-label">Current Loss</div></div>
                    <div class="stat"><div class="stat-value">${improvement}%</div><div class="stat-label">Improvement</div></div>
                    <div class="stat"><div class="stat-value">${data.avg_change ? data.avg_change.toFixed(4) : 'N/A'}</div><div class="stat-label">Change (4 epochs)</div></div>
                `;

                // Update status
                if (data.converged) {
                    document.getElementById('status').innerHTML = '✅ CONVERGED';
                    document.getElementById('status').style.color = '#0f0';
                } else if (data.avg_change && data.avg_change < 0.01) {
                    document.getElementById('status').innerHTML = '⚠️ NEARLY CONVERGED';
                    document.getElementById('status').style.color = '#ff0';
                }

                // Plot
                Plotly.newPlot('chart', [{
                    x: epochs,
                    y: losses,
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: {color: '#0ff', width: 3},
                    marker: {size: 8, color: '#0f0'}
                }], {
                    title: {text: 'Training Loss', font: {color: '#0ff'}},
                    paper_bgcolor: '#000',
                    plot_bgcolor: '#111',
                    font: {color: '#0f0'},
                    xaxis: {title: 'Epoch', gridcolor: '#333'},
                    yaxis: {title: 'Loss', gridcolor: '#333'},
                    height: 500
                });
            } catch (e) {
                console.error(e);
            }
        }

        update();
        setInterval(update, 10000);
    </script>
</body>
</html>
"""


Handler = DashboardHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Dashboard server at http://localhost:{PORT}")
    httpd.serve_forever()
