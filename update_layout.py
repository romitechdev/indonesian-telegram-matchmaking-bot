import os
import re

def update_sidebar(html):
    new_sidebar = """    <aside class="sidebar">
      <h2>LoveMatchID</h2>
      <nav>
        <a href="/">Dashboard</a>
        <a href="/users">Daftar User</a>
        <a href="/reports">Daftar Report</a>
        <a href="/matches">Riwayat Match</a>
        <a href="/chats">Active Chats</a>
        <form class="logout-form" method="post" action="/logout">
          <button type="submit" class="logout-btn">Logout</button>
        </form>
      </nav>
    </aside>"""
    
    # replace existing sidebar
    html = re.sub(r'<aside class="sidebar">.*?</aside>', new_sidebar, html, flags=re.DOTALL)
    
    # remove inline logout forms if any left (shouldn't be, but just in case)
    return html

for template in ['dashboard.html', 'users.html', 'reports.html', 'matches.html', 'chats.html', 'chat_transcript.html', 'match_detail.html', 'user_detail.html']:
    path = os.path.join('templates', template)
    if not os.path.exists(path): continue
    
    with open(path, 'r') as f:
        html = f.read()
        
    html = update_sidebar(html)
    
    # Now customize specific files
    if template == 'dashboard.html':
        # keep only statistics, active chats chips. 
        # remove users section and reports section
        html = re.sub(r'<div class="section">\s*<h2>20 User Terbaru</h2>.*?</div>\s*(<div class="section">)', r'\1', html, flags=re.DOTALL)
        html = re.sub(r'<hr style="border-color:var\(--border\); margin:12px 0;"/>\s*<h2>20 Report Terbaru</h2>.*?</div>\s*</div>', r'</div>\n  </div>', html, flags=re.DOTALL)
        # remove the bulk action script
        html = re.sub(r'<script>.*?</script>', '', html, flags=re.DOTALL)
        
    elif template == 'users.html':
        # keep ONLY the users table
        # remove the top cards, chips
        html = re.sub(r'<div class="cards">.*?</div>\s*<div class="section">\s*<h2>Distribusi Gender</h2>.*?</div>\s*<div class="section">', r'<div class="section">', html, flags=re.DOTALL)
        # remove active chats and reports at the bottom
        html = re.sub(r'</div>\s*<div class="section">\s*<h2>Active Chats</h2>.*?</div>\s*</div>', r'</div>\n  </div>', html, flags=re.DOTALL)
        
        # Rewrite the table
        old_table = r'<form method="post" action="/users/bulk-action" id="bulk-users-form">.*?</form>'
        new_table = """
        <table>
        <thead>
          <tr>
            <th>Nama</th>
            <th>Umur</th>
            <th>Gender</th>
            <th>Telegram ID</th>
            <th>Status</th>
            <th>Aksi</th>
          </tr>
        </thead>
        <tbody>
          {% for user in users %}
            <tr>
              <td>{{ user.name }}</td>
              <td>{{ user.age }}</td>
              <td>{{ user.gender }}</td>
              <td>{{ user.telegram_id }}</td>
              <td>
                {% if user.is_banned %}<span class="status-warn">Banned</span>{% elif user.active %}<span class="status-ok">Aktif</span>{% else %}<span class="status-idle">Nonaktif</span>{% endif %}
              </td>
              <td>
                <form class="inline-form" method="post" action="/users/bulk-action">
                  <input type="hidden" name="selected_user_ids" value="{{ user.id }}">
                  <input type="hidden" name="page" value="{{ user_page.page }}">
                  <input type="hidden" name="next" value="users">
                  
                  <a class="btn-link" href="/users/{{ user.id }}" style="padding: 2px 6px; font-size: 11px;">Detail</a>
                  
                  {% if user.is_banned %}
                    <button class="mini-btn ok" type="submit" name="action" value="unban">Unban</button>
                  {% else %}
                    <button class="mini-btn warn" type="submit" name="action" value="ban">Ban</button>
                  {% endif %}
                  <button class="mini-btn warn" type="submit" name="action" value="delete" style="background:var(--bad-bg); color:white;" onclick="return confirm('Hapus user ini?')">Hapus</button>
                </form>
              </td>
            </tr>
          {% else %}
            <tr><td colspan="6">Belum ada user.</td></tr>
          {% endfor %}
        </tbody>
        </table>
        """
        html = re.sub(old_table, new_table, html, flags=re.DOTALL)
        
        # update title
        html = html.replace('<h2>20 User Terbaru</h2>', '<h2>Daftar User</h2>')
        
    elif template == 'reports.html':
        # keep ONLY the reports table
        # remove everything before reports section
        html = re.sub(r'<div class="cards">.*?(<hr style="border-color:var\(--border\); margin:12px 0;"/>\s*<h2>20 Report Terbaru</h2>)', r'\1', html, flags=re.DOTALL)
        html = html.replace('<hr style="border-color:var(--border); margin:12px 0;"/>\n\n      <h2>20 Report Terbaru</h2>', '<div class="section">\n<h2>Daftar Report</h2>')
        html = html.replace('<h2>20 Report Terbaru</h2>', '<div class="section">\n<h2>Daftar Report</h2>')
        # make sure it closes section correctly
        # no need to change table, it's already there
        
    with open(path, 'w') as f:
        f.write(html)
