import os
import re

css = """  <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
    
    :root {
      --bg: #f4f4f0;
      --panel: #ffffff;
      --border: #111111;
      --text: #111111;
      --muted: #555555;
      --good: #000000;
      --good-bg: #4ade80;
      --warn: #000000;
      --warn-bg: #fde047;
      --bad: #ffffff;
      --bad-bg: #ef4444;
      --chip: #e0e0e0;
      --primary: #3b82f6;
      --shadow-sm: 2px 2px 0px var(--border);
      --shadow-md: 4px 4px 0px var(--border);
      --shadow-lg: 6px 6px 0px var(--border);
    }

    * { box-sizing: border-box; }
    
    body {
      margin: 0;
      background: var(--bg);
      background-image: radial-gradient(#cbd5e1 2px, transparent 2px);
      background-size: 24px 24px;
      color: var(--text);
      font-family: 'Space Grotesk', system-ui, sans-serif;
      line-height: 1.5;
    }

    h1, h2, h3 {
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: -0.02em;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }

    /* Topbar */
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 32px;
      background: var(--panel);
      padding: 20px;
      border: 3px solid var(--border);
      box-shadow: var(--shadow-md);
    }
    .topbar h1 { margin: 0 0 4px; font-size: 28px; background: var(--warn-bg); display: inline-block; padding: 0 8px; border: 2px solid var(--border); }
    .sub { color: var(--muted); margin: 0; font-weight: 600; font-size: 14px; }

    /* Buttons */
    button, .btn-link, .logout-btn {
      border: 3px solid var(--border);
      background: var(--panel);
      color: var(--text);
      cursor: pointer;
      font-weight: 700;
      font-family: inherit;
      padding: 8px 16px;
      box-shadow: var(--shadow-sm);
      transition: all 0.1s ease-in-out;
      text-decoration: none;
      display: inline-block;
      text-transform: uppercase;
      font-size: 13px;
    }
    button:hover, .btn-link:hover, .logout-btn:hover {
      transform: translate(-2px, -2px);
      box-shadow: var(--shadow-md);
    }
    button:active, .btn-link:active, .logout-btn:active {
      transform: translate(2px, 2px);
      box-shadow: 0px 0px 0px var(--border);
    }
    
    .logout-btn { background: var(--bad-bg); color: var(--bad); }

    /* Cards */
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }
    .card {
      border: 3px solid var(--border);
      background: var(--panel);
      padding: 20px;
      box-shadow: var(--shadow-md);
      transition: transform 0.2s;
    }
    .card:hover {
      transform: translateY(-4px);
      box-shadow: var(--shadow-lg);
    }
    .card .label { font-weight: 700; font-size: 14px; text-transform: uppercase; border-bottom: 2px solid var(--border); padding-bottom: 4px; margin-bottom: 8px; }
    .card .value { font-size: 36px; font-weight: 700; }

    /* Sections */
    .section, .panel {
      border: 3px solid var(--border);
      background: var(--panel);
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-md);
    }
    .section h2 { margin: 0 0 16px; font-size: 22px; display: inline-block; border-bottom: 4px solid var(--primary); }

    /* Chips */
    .chips { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
    .chip {
      background: var(--chip);
      border: 2px solid var(--border);
      padding: 6px 12px;
      font-size: 14px;
      font-weight: 600;
      box-shadow: 2px 2px 0px var(--border);
      text-transform: uppercase;
    }

    /* Tables */
    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 14px;
      border: 3px solid var(--border);
      background: var(--panel);
      box-shadow: var(--shadow-md);
      margin-top: 16px;
      display: block;
      overflow-x: auto;
    }
    thead th {
      text-align: left;
      background: var(--border);
      color: var(--panel);
      font-weight: 700;
      padding: 12px;
      text-transform: uppercase;
      white-space: nowrap;
    }
    tbody td {
      border-bottom: 2px solid var(--border);
      border-right: 2px solid var(--border);
      padding: 12px;
      white-space: nowrap;
      font-weight: 600;
    }
    tbody tr td:last-child { border-right: none; }
    tbody tr:last-child td { border-bottom: none; }
    tbody tr:nth-child(even) { background: #f8fafc; }
    tbody tr:hover { background: #fef08a; }

    /* Status Colors */
    .status-ok { background: var(--good-bg); color: var(--good); padding: 2px 6px; border: 2px solid var(--border); font-weight: 700; display: inline-block;}
    .status-warn { background: var(--warn-bg); color: var(--warn); padding: 2px 6px; border: 2px solid var(--border); font-weight: 700; display: inline-block;}
    .status-bad { background: var(--bad-bg); color: var(--bad); padding: 2px 6px; border: 2px solid var(--border); font-weight: 700; display: inline-block;}
    
    .status-live { background: var(--good-bg); color: var(--good); padding: 4px 8px; border: 2px solid var(--border); font-weight: 700; box-shadow: 2px 2px 0px var(--border);}
    .status-idle { background: var(--chip); color: var(--text); padding: 4px 8px; border: 2px solid var(--border); font-weight: 700; box-shadow: 2px 2px 0px var(--border);}

    /* Forms & Inputs */
    input, select, textarea {
      border: 3px solid var(--border);
      background: #ffffff;
      color: var(--text);
      padding: 10px 14px;
      font-size: 14px;
      font-weight: 600;
      font-family: inherit;
      box-shadow: var(--shadow-sm);
      outline: none;
    }
    input:focus, select:focus { box-shadow: var(--shadow-md); transform: translate(-2px, -2px); }

    .bulk-toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      background: #e2e8f0;
      padding: 12px;
      border: 3px solid var(--border);
    }
    .bulk-toolbar button { background: var(--primary); color: #fff; }

    /* Notices */
    .hint { margin-top: 12px; color: var(--text); font-size: 13px; font-weight: 600; border-left: 4px solid var(--primary); padding-left: 8px; }
    .notice {
      border: 3px solid var(--border);
      padding: 12px 16px;
      margin-bottom: 20px;
      font-size: 15px;
      font-weight: 700;
      box-shadow: var(--shadow-sm);
    }
    .notice-ok { background: var(--good-bg); color: var(--good); }
    .notice-warn { background: var(--warn-bg); color: var(--warn); }
    .notice-error, .notice-bad { background: var(--bad-bg); color: var(--bad); }

    /* Utilities */
    a { color: var(--border); text-decoration: underline; font-weight: 700; }
    a:hover { background: var(--warn-bg); text-decoration: none; }
    
    .inline-form { display: inline-flex; gap: 8px; margin: 0; }
    
    .mini-btn { padding: 4px 10px; font-size: 12px; }
    .mini-btn.ok { background: var(--good-bg); color: var(--good); }
    .mini-btn.warn { background: var(--bad-bg); color: var(--bad); }

    .pagination {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 20px;
      flex-wrap: wrap;
      background: var(--panel);
      padding: 12px;
      border: 3px solid var(--border);
      box-shadow: var(--shadow-sm);
    }
    .pagination .page-info { font-weight: 700; font-size: 14px; text-transform: uppercase; }

    /* Specific to detail pages */
    .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
    .item { border: 3px solid var(--border); padding: 16px; background: #fafafa; box-shadow: var(--shadow-sm); }
    .item .label { font-weight: 700; font-size: 13px; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; border-bottom: 2px solid var(--border); padding-bottom: 4px; }
    .item .value { font-size: 16px; font-weight: 700; }

    .msg { border: 3px solid var(--border); margin-bottom: 12px; background: #fff; box-shadow: var(--shadow-sm); padding: 0; }
    .msg .sender { background: var(--border); color: #fff; padding: 6px 12px; font-weight: 700; font-size: 13px; }
    .msg .time { padding: 4px 12px; font-size: 12px; background: #f1f5f9; border-bottom: 2px solid var(--border); font-weight: 600; }
    .msg pre { margin: 0; padding: 12px; white-space: pre-wrap; word-break: break-word; font-family: 'Space Grotesk', monospace; font-weight: 600; font-size: 14px; }
    .msg img { border: 3px solid var(--border); border-radius: 0 !important; box-shadow: 2px 2px 0px var(--border); }
    .msg .photo-container { padding: 12px 12px 0 12px; }

    /* Login Specific */
    .login-panel { width: min(420px, calc(100vw - 32px)); margin: 10vh auto; }
    form label { font-weight: 700; text-transform: uppercase; font-size: 14px; margin-top: 8px; display: block;}
    form input { margin-top: 4px; margin-bottom: 12px; width: 100%;}
    form button[type="submit"] { width: 100%; padding: 12px; font-size: 16px; background: var(--primary); color: #fff;}
  </style>"""

for f in os.listdir('templates'):
    if f.endswith('.html'):
        path = os.path.join('templates', f)
        with open(path, 'r') as file:
            content = file.read()
        
        # Replace everything between <style> and </style>
        new_content = re.sub(r'<style>.*?</style>', css, content, flags=re.DOTALL)
        
        # for login.html we need to make sure the panel class has login-panel or just panel works. 
        # Actually our CSS styles .panel and .login-panel
        with open(path, 'w') as file:
            file.write(new_content)

print("CSS updated in all templates")
