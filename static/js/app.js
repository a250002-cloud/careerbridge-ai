/**
 * app.js – CareerBridge AI SPA v2 (enhanced UI)
 * Sidebar layout, page transitions, improved all pages.
 */

/* ── State ─────────────────────────────────────────────────────────────────── */
const State = { user: null, chatSessionId: null };

/* ── Router ─────────────────────────────────────────────────────────────────── */
const routes = {};
function route(path, fn) { routes[path] = fn; }
function navigate(path, replace = false) {
  if (replace) history.replaceState({}, '', path);
  else         history.pushState({}, '', path);
  render();
}
window.addEventListener('popstate', render);
function render() {
  const fn = routes[location.pathname] || routes['*'];
  if (fn) {
    try {
      const result = fn();
      if (result && typeof result.catch === 'function') {
        result.catch(err => {
          console.error('Route error:', err);
          const msg = String(err?.message || err).replace(/</g,'&lt;').replace(/>/g,'&gt;');
          document.getElementById('app').innerHTML =
            '<div style="padding:60px;text-align:center;font-family:system-ui">' +
            '<h2 style="color:#dc2626">Something went wrong</h2>' +
            '<p style="color:#64748b;margin:12px 0">' + msg + '</p>' +
            '<a href="/" style="color:#2563eb;cursor:pointer" onclick="location.reload()">Reload page</a>' +
            '</div>';
        });
      }
    } catch (err) {
      console.error('Route error:', err);
    }
  }
}

/* ── Helpers ─────────────────────────────────────────────────────────────────── */
function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function mount(html) {
  document.getElementById('app').innerHTML = html;
  // Page transition
  const main = document.querySelector('.main-content, .page-full, .page-auth');
  if (main) { main.classList.remove('page-enter'); void main.offsetWidth; main.classList.add('page-enter'); }
  // Wire nav links (SPA navigation)
  document.querySelectorAll('[data-nav]').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      navigate(el.getAttribute('data-nav') || el.getAttribute('href'));
    });
  });
  // Active sidebar link
  document.querySelectorAll('.sidebar-link').forEach(el => {
    const href = el.getAttribute('data-nav') || el.getAttribute('href');
    if (href === location.pathname) el.classList.add('active');
    else el.classList.remove('active');
  });
}
function showAlert(container, type, message) {
  const a = document.createElement('div');
  a.className = `alert alert-${type}`;
  a.textContent = message;
  container.prepend(a);
  setTimeout(() => a.remove(), 6000);
}
function bandBadge(band) {
  const map = {
    strong_match: ['band-strong','⭐ Strong Match'],
    good_match:   ['band-good','✓ Good Match'],
    exploratory:  ['band-explore','→ Exploratory'],
  };
  const [cls, lbl] = map[band] || ['badge-muted', band||'Unknown'];
  return `<span class="${cls}">${lbl}</span>`;
}
function statusBadge(s) {
  const map = { strong:'badge-success', partial:'badge-warn', gap:'badge-danger' };
  return `<span class="badge ${map[s]||'badge-muted'}">${s||'?'}</span>`;
}
function priorityBadge(p) {
  const map = { high:'badge-danger', medium:'badge-warn', low:'badge-info' };
  return `<span class="badge ${map[p]||'badge-muted'}">${p||'?'}</span>`;
}
function renderMarkdown(text) {
  return String(text||'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/^[•\-]\s+(.+)$/gm,'<li>$1</li>')
    .replace(/^(\d+)\.\s+(.+)$/gm,'<li>$2</li>')
    .replace(/(<li>[\s\S]*?<\/li>)+/g, m=>`<ul style="padding-left:18px;margin:6px 0">${m}</ul>`)
    .replace(/\n/g,'<br>');
}
async function checkAuth() {
  const res = await API.me();
  if (res.ok && res.data.user && res.data.user.id) {
    State.user = res.data.user;
    return true;
  }
  State.user = null;
  return false;
}
function requireAuth() { if (!State.user) { navigate('/login'); return false; } return true; }
function initials(name) { return (name||'?').split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2); }

/* ── Topbar builders ─────────────────────────────────────────────────────────── */
function publicTopbar() {
  return `
  <div class="topbar">
    <a class="logo" href="/" data-nav="/">
      <div class="logo-icon">🎯</div>
      Career<span>Bridge</span> AI
    </a>
    <nav>
      <a href="/login" data-nav="/login">Sign in</a>
      <a href="/register" class="btn-register" data-nav="/register">Get Started</a>
    </nav>
  </div>`;
}
function appTopbar() {
  const u = State.user;
  return `
  <div class="topbar">
    <a class="logo" href="/dashboard" data-nav="/dashboard">
      <div class="logo-icon">🎯</div>
      Career<span>Bridge</span> AI
    </a>
    <div class="topbar-user">
      <div class="user-avatar">${initials(u?.name)}</div>
      <span class="user-name">${escHtml(u?.name||'')}</span>
      <button class="logout-btn" id="logout-btn">Sign out</button>
    </div>
  </div>`;
}
function sidebar() {
  const links = [
    { href:'/dashboard',  icon:'🏠', label:'Dashboard' },
    { href:'/upload',     icon:'📄', label:'Resume Upload' },
    { href:'/matches',    icon:'🎯', label:'Career Matches' },
    { href:'/gap',        icon:'📊', label:'Skill Gaps' },
    { href:'/roadmap',    icon:'🗺️', label:'Roadmap' },
    null, // divider
    { href:'/copilot',    icon:'🤖', label:'AI Copilot' },
    { href:'/builder',    icon:'📝', label:'Resume Builder' },
    { href:'/interview',  icon:'🎤', label:'Interview Prep' },
    null,
    { href:'/profile',    icon:'👤', label:'Profile & Settings' },
  ];
  const html = links.map(l => l === null
    ? `<div class="sidebar-divider"></div>`
    : `<a class="sidebar-link${l.href===location.pathname?' active':''}" href="${l.href}" data-nav="${l.href}">
        <span class="icon">${l.icon}</span><span class="label">${l.label}</span>
       </a>`
  ).join('');
  return `<nav class="sidebar">${html}</nav>`;
}
function appShell(contentHtml) {
  return `
    ${appTopbar()}
    <div class="app-layout">
      ${sidebar()}
      <main class="main-content page-enter">${contentHtml}</main>
    </div>`;
}
function loadingShell(msg='Loading…') {
  return appShell(`<div class="loading-overlay">
    <div class="spinner spinner-lg"></div>
    <p>${msg}</p>
  </div>`);
}

/* ═══════════════════════════════════════════════════════════════════════════
   LANDING
═══════════════════════════════════════════════════════════════════════════ */
route('/', async () => {
  await checkAuth();
  if (State.user) { navigate('/dashboard', true); return; }

  mount(`
    ${publicTopbar()}
    <div class="page-full">
      <div class="hero">
        <div class="hero-eyebrow">✨ AI-Powered Career Intelligence</div>
        <h1>Your career path,<br/><span class="gradient-text">clarified by AI</span></h1>
        <p class="hero-sub">Upload your resume, discover the tech roles that fit you best, see exactly what skills you're missing, and follow a prerequisite-ordered learning roadmap — all in one place.</p>
        <div class="hero-cta">
          <a href="/register" data-nav="/register" class="btn btn-primary btn-xl">Get Started Free</a>
          <a href="/login"    data-nav="/login"    class="btn-outline-white">Sign In →</a>
        </div>
        <div class="hero-stats">
          <div class="hero-stat"><div class="num">10</div><div class="lbl">Tech Roles Analyzed</div></div>
          <div class="hero-stat"><div class="num">50+</div><div class="lbl">Skills in Knowledge Base</div></div>
          <div class="hero-stat"><div class="num">100%</div><div class="lbl">Free to Use</div></div>
        </div>
      </div>

      <div class="journey-section">
        <div style="text-align:center;margin-bottom:36px">
          <h2 style="font-size:26px;font-weight:800;letter-spacing:-.3px">How it works</h2>
          <p style="font-size:14px;color:var(--muted);margin-top:8px">From resume to job-ready in minutes</p>
        </div>
        <div class="journey-steps">
          ${[
            ['📄','Upload Resume','PDF or DOCX'],
            ['🔍','Review Profile','Confirm skills'],
            ['🎯','Get Matches','10 tech roles ranked'],
            ['📊','See Gaps','Role-specific gaps'],
            ['🗺️','Follow Roadmap','Learn in order'],
            ['🤖','Use Copilot','AI guidance'],
          ].map(([icon,label,sub])=>`
            <div class="journey-step">
              <div class="js-icon">${icon}</div>
              <div class="js-label">${label}</div>
              <div class="js-sub">${sub}</div>
            </div>`).join('')}
        </div>
      </div>

      <div class="features-section">
        <div class="features-header">
          <h2>Everything you need to launch your tech career</h2>
          <p>A complete career intelligence platform — not a job board, not a generic chatbot.</p>
        </div>
        <div class="features-grid">
          ${[
            ['si-blue','📄','Smart Resume Parsing','Extracts skills from PDF/DOCX with evidence-based confidence scores, section detection, and mandatory review before analysis.'],
            ['si-purple','🎯','Career Role Matching','Ranked matches across Python Developer, Backend, Frontend, Full Stack, Data Analyst, Data Scientist, ML Engineer and more.'],
            ['si-orange','📊','Skill Gap Analysis','See Strong / Improving / Gap status for every required skill, with a career readiness indicator.'],
            ['si-green','🗺️','Prerequisite Roadmap','Topologically sorted learning plan — prerequisites always come first. Progress tracked automatically.'],
            ['si-blue','🤖','AI Career Copilot','Context-aware chat that references your actual skills and gaps. Works offline with a smart fallback.'],
            ['si-purple','📝','Resume Builder','Generate ATS-friendly PDFs from 3 professional templates with AI wording suggestions.'],
          ].map(([si,icon,title,desc])=>`
            <div class="feature-card">
              <div class="fc-icon ${si}">${icon}</div>
              <h3>${title}</h3>
              <p>${desc}</p>
            </div>`).join('')}
        </div>
      </div>

      <div class="landing-footer">
        CareerBridge AI · Resume → Match → Gap → Roadmap · Guidance only, not employment guarantees
      </div>
    </div>`);
});

/* ═══════════════════════════════════════════════════════════════════════════
   REGISTER
═══════════════════════════════════════════════════════════════════════════ */
route('/register', async () => {
  await checkAuth();
  if (State.user) { navigate('/dashboard', true); return; }

  mount(`
    ${publicTopbar()}
    <div class="page-auth">
      <div class="page-auth-box">
        <div style="text-align:center;margin-bottom:28px">
          <div style="font-size:32px;margin-bottom:8px">🎯</div>
          <h1 style="font-size:20px;font-weight:800;letter-spacing:-.3px">Create your account</h1>
          <p style="font-size:13px;color:var(--muted);margin-top:4px">Start your career intelligence journey</p>
        </div>
        <div id="reg-alerts"></div>
        <form id="reg-form">
          <div class="form-group">
            <label>Full Name</label>
            <input type="text" id="reg-name" class="form-control" placeholder="Jane Smith" required />
          </div>
          <div class="form-group">
            <label>Email Address</label>
            <input type="email" id="reg-email" class="form-control" placeholder="jane@example.com" required />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" id="reg-pwd" class="form-control" placeholder="Min. 8 characters" required minlength="8" />
          </div>
          <button type="submit" class="btn btn-primary btn-block" style="padding:11px;font-size:14px" id="reg-btn">
            Create Account →
          </button>
        </form>
        <p style="text-align:center;margin-top:20px;font-size:13px;color:var(--muted)">
          Already have an account? <a href="/login" data-nav="/login">Sign in</a>
        </p>
      </div>
    </div>`);

  document.getElementById('reg-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('reg-btn');
    btn.textContent = 'Creating…'; btn.disabled = true;
    const res = await API.register({
      name: document.getElementById('reg-name').value,
      email: document.getElementById('reg-email').value,
      password: document.getElementById('reg-pwd').value,
    });
    btn.textContent = 'Create Account →'; btn.disabled = false;
    if (res.ok) { State.user = res.data.user; navigate('/upload'); }
    else showAlert(document.getElementById('reg-alerts'), 'danger', res.error?.message || 'Registration failed.');
  });
});

/* ═══════════════════════════════════════════════════════════════════════════
   LOGIN
═══════════════════════════════════════════════════════════════════════════ */
route('/login', async () => {
  await checkAuth();
  if (State.user) { navigate('/dashboard', true); return; }

  mount(`
    ${publicTopbar()}
    <div class="page-auth">
      <div class="page-auth-box">
        <div style="text-align:center;margin-bottom:28px">
          <div style="font-size:32px;margin-bottom:8px">👋</div>
          <h1 style="font-size:20px;font-weight:800;letter-spacing:-.3px">Welcome back</h1>
          <p style="font-size:13px;color:var(--muted);margin-top:4px">Sign in to your CareerBridge account</p>
        </div>
        <div id="login-alerts"></div>
        <form id="login-form">
          <div class="form-group">
            <label>Email Address</label>
            <input type="email" id="login-email" class="form-control" required autofocus />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" id="login-pwd" class="form-control" required />
          </div>
          <button type="submit" class="btn btn-primary btn-block" style="padding:11px;font-size:14px" id="login-btn">
            Sign In →
          </button>
        </form>
        <p style="text-align:center;margin-top:20px;font-size:13px;color:var(--muted)">
          New here? <a href="/register" data-nav="/register">Create account</a>
        </p>
      </div>
    </div>`);

  document.getElementById('login-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    btn.textContent = 'Signing in…'; btn.disabled = true;
    const res = await API.login({
      email: document.getElementById('login-email').value,
      password: document.getElementById('login-pwd').value,
    });
    btn.textContent = 'Sign In →'; btn.disabled = false;
    if (res.ok) { State.user = res.data.user; navigate('/dashboard'); }
    else showAlert(document.getElementById('login-alerts'), 'danger', res.error?.message || 'Invalid credentials.');
  });
});

/* ═══════════════════════════════════════════════════════════════════════════
   DASHBOARD
═══════════════════════════════════════════════════════════════════════════ */
route('/dashboard', async () => {
  if (!await checkAuth()) return;
  mount(loadingShell('Loading dashboard…'));
  attachLogout();

  const [profileRes, progressRes, recRes] = await Promise.all([
    API.getProfile(), API.getProgress(), API.getRecommendations(false)
  ]);

  const user   = profileRes.data?.user || State.user;
  const target = profileRes.data?.profile?.target_role;
  const prog   = progressRes.data || {};
  const recs   = recRes.data?.recommendations || [];
  const topMatch = recs[0];

  mount(appShell(`
    <div class="page-header">
      <div class="page-title">Welcome back, ${escHtml(user?.name?.split(' ')[0] || 'there')} 👋</div>
      <div class="page-sub">Here's your career journey at a glance.</div>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon si-blue">🎯</div>
        <div class="stat-label">Target Role</div>
        <div class="stat-value" style="font-size:17px;letter-spacing:-.2px">${target ? escHtml(target.name) : '—'}</div>
        <div class="stat-sub">${target ? 'Currently targeting' : 'Not yet selected'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon si-green">📈</div>
        <div class="stat-label">Roadmap Progress</div>
        <div class="stat-value">${prog.progress_pct || 0}<span style="font-size:14px;font-weight:500">%</span></div>
        <div class="stat-sub">${prog.completed || 0} of ${prog.total || 0} items done</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon si-purple">⭐</div>
        <div class="stat-label">Top Match</div>
        <div class="stat-value" style="font-size:17px;letter-spacing:-.2px">${topMatch ? escHtml(topMatch.role_name) : '—'}</div>
        <div class="stat-sub">${topMatch ? bandBadge(topMatch.band) : 'Upload resume first'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon si-orange">🔍</div>
        <div class="stat-label">Roles Analyzed</div>
        <div class="stat-value">${recs.length}</div>
        <div class="stat-sub">out of 10 tech roles</div>
      </div>
    </div>

    ${prog.total > 0 ? `
    <div class="card card-flat" style="margin-bottom:20px">
      <div class="flex justify-between items-center mb-8">
        <span style="font-size:13px;font-weight:600">Roadmap Progress</span>
        <span style="font-size:13px;font-weight:700;color:var(--accent)">${prog.progress_pct||0}%</span>
      </div>
      <div class="progress-bar"><div class="progress-fill green" style="width:${prog.progress_pct||0}%"></div></div>
      <p class="text-xs text-muted mt-8">${prog.completed} completed · ${prog.in_progress||0} in progress · ${(prog.total||0)-(prog.completed||0)-(prog.in_progress||0)} pending</p>
    </div>` : ''}

    <div class="grid-2">
      <div>
        <div style="font-size:13px;font-weight:700;margin-bottom:12px;color:var(--muted)">QUICK ACTIONS</div>
        <div class="card card-flat" style="padding:16px">
          <div style="display:flex;flex-direction:column;gap:8px">
            <a href="/upload"    data-nav="/upload"    class="btn btn-secondary" style="justify-content:flex-start">📄 Upload / Update Resume</a>
            <a href="/matches"   data-nav="/matches"   class="btn btn-secondary" style="justify-content:flex-start">🎯 View Career Matches</a>
            <a href="/roadmap"   data-nav="/roadmap"   class="btn btn-secondary" style="justify-content:flex-start">🗺️ My Learning Roadmap</a>
            <a href="/copilot"   data-nav="/copilot"   class="btn btn-ghost"     style="justify-content:flex-start">🤖 Chat with AI Copilot</a>
          </div>
        </div>
      </div>
      <div>
        <div style="font-size:13px;font-weight:700;margin-bottom:12px;color:var(--muted)">TOP CAREER MATCHES</div>
        ${recs.length ? recs.slice(0,4).map((r,i) => `
          <div class="card card-flat" style="padding:14px 16px;cursor:pointer;margin-bottom:8px" onclick="navigate('/matches')">
            <div class="flex justify-between items-center">
              <div>
                <div style="font-size:12px;color:var(--muted);font-weight:700">#${i+1}</div>
                <div style="font-weight:700;font-size:14px">${escHtml(r.role_name)}</div>
              </div>
              ${bandBadge(r.band)}
            </div>
          </div>`).join('')
        : `<div class="empty-state" style="padding:24px">
            <div class="es-icon">📄</div>
            <h3>No matches yet</h3>
            <p>Upload and confirm your resume to see career matches.</p>
            <a href="/upload" data-nav="/upload" class="btn btn-primary btn-sm">Upload Resume</a>
           </div>`}
      </div>
    </div>`));
  attachLogout();
});

/* ═══════════════════════════════════════════════════════════════════════════
   RESUME UPLOAD
═══════════════════════════════════════════════════════════════════════════ */
route('/upload', async () => {
  if (!await checkAuth()) return;

  mount(appShell(`
    <div class="page-header">
      <div class="page-title">Upload Your Resume</div>
      <div class="page-sub">PDF or DOCX · Max 5 MB · Max 10 pages</div>
    </div>
    <div id="upload-alerts"></div>
    <div class="card" style="max-width:600px">
      <div class="upload-zone" id="upload-zone">
        <div class="upload-icon">☁️</div>
        <h3>Drop your resume here</h3>
        <p>or <span class="browse-link" id="browse-link">browse files</span></p>
        <div class="upload-meta">Supported: PDF, DOCX · Max 5 MB</div>
        <input type="file" id="file-input" accept=".pdf,.docx" style="display:none" />
      </div>
      <div id="upload-progress" class="hidden" style="text-align:center;padding:32px">
        <div class="spinner spinner-lg" style="margin:0 auto 12px"></div>
        <p style="font-size:14px;font-weight:600;color:var(--text)">Parsing your resume…</p>
        <p class="text-sm text-muted mt-4">Extracting skills, sections and education</p>
      </div>
    </div>
    <div class="card" style="max-width:600px;background:var(--surface)">
      <p style="font-size:13px;font-weight:600;margin-bottom:8px">What happens next?</p>
      <div style="display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--muted)">
        <span>① Skills are extracted with confidence scores from each section</span>
        <span>② You review and confirm the profile before any analysis runs</span>
        <span>③ Career matches, gap analysis and roadmap are generated</span>
      </div>
    </div>`));
  attachLogout();

  const zone = document.getElementById('upload-zone');
  const input = document.getElementById('file-input');
  document.getElementById('browse-link').onclick = () => input.click();
  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) doUpload(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => { if (input.files[0]) doUpload(input.files[0]); });

  async function doUpload(file) {
    const prog = document.getElementById('upload-progress');
    zone.style.display = 'none'; prog.classList.remove('hidden');
    const fd = new FormData(); fd.append('file', file);
    const res = await API.uploadResume(fd);
    prog.classList.add('hidden'); zone.style.display = '';
    if (res.ok) navigate(`/review?id=${res.data.resume_id}`);
    else showAlert(document.getElementById('upload-alerts'), 'danger', res.error?.message || 'Upload failed. Please try again.');
  }
});

/* ═══════════════════════════════════════════════════════════════════════════
   REVIEW & CONFIRM
═══════════════════════════════════════════════════════════════════════════ */
route('/review', async () => {
  if (!await checkAuth()) return;
  const resumeId = new URLSearchParams(location.search).get('id');
  if (!resumeId) { navigate('/upload'); return; }

  mount(loadingShell('Loading extracted profile…'));
  attachLogout();

  const res = await API.getResume(resumeId);
  if (!res.ok) { navigate('/upload'); return; }

  const { file_name, analysis } = res.data;
  const profile = analysis?.profile || {};
  let skillsState = (profile.skills || []).map(s => ({...s}));

  function renderSkillTags() {
    return skillsState.map((s, i) => {
      const conf = s.confidence || 0;
      const dot = conf >= 0.7 ? 'conf-strong' : conf >= 0.4 ? 'conf-partial' : 'conf-gap';
      const src = s.source === 'self_reported' ? ' · self-reported' : s.section ? ` · ${s.section}` : '';
      return `<span class="skill-tag" id="st-${i}">
        <span class="conf-dot ${dot}"></span>
        ${escHtml(s.canonical_name || `skill_${s.skill_id}`)}
        <span style="color:var(--muted-2);font-size:11px">${src}</span>
        <button onclick="removeSkill(${i})" style="background:none;border:none;cursor:pointer;color:var(--danger);padding:0 2px;font-size:13px;line-height:1">×</button>
      </span>`;
    }).join('');
  }

  mount(appShell(`
    <div class="page-header-row">
      <div>
        <div class="page-title">Review Extracted Profile</div>
        <div class="page-sub">From: <strong>${escHtml(file_name)}</strong> — Confirm before analysis runs</div>
      </div>
      <a href="/upload" data-nav="/upload" class="btn btn-secondary btn-sm">← Re-upload</a>
    </div>

    <div class="alert alert-info">
      Review your extracted skills below. Remove any that are incorrect, add missing ones, then click <strong>Confirm Profile</strong>.
      Analysis cannot run on an unconfirmed profile.
    </div>
    <div id="review-alerts"></div>

    <div class="grid-2">
      <div>
        <div class="card">
          <div class="card-header">
            <h2>Extracted Skills <span class="badge badge-info" id="skill-count">${skillsState.length}</span></h2>
          </div>
          <div id="skills-container">${renderSkillTags()}</div>
          <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
            <select id="skill-select" class="form-control" style="flex:1;min-width:160px">
              <option value="">— Add a skill manually —</option>
            </select>
            <button class="btn btn-secondary btn-sm" id="add-skill-btn">+ Add</button>
          </div>
          <div class="mt-12" style="display:flex;gap:8px;flex-wrap:wrap">
            <span style="font-size:12px;color:var(--muted)">Legend:</span>
            <span class="skill-tag"><span class="conf-dot conf-strong"></span>Strong (≥70%)</span>
            <span class="skill-tag"><span class="conf-dot conf-partial"></span>Partial (40–70%)</span>
            <span class="skill-tag"><span class="conf-dot conf-gap"></span>Low (&lt;40%)</span>
          </div>
        </div>

        <div class="card">
          <div class="card-header"><h2>Education Detected</h2></div>
          ${(profile.education||[]).length
            ? (profile.education||[]).map(e=>`<p class="text-sm" style="margin-bottom:6px">🎓 ${escHtml(e.raw||e)}</p>`).join('')
            : '<p class="text-sm text-muted">None detected</p>'}
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-header"><h2>Section Detection</h2></div>
          ${Object.entries(profile.section_confidence||{}).map(([sec, conf])=>`
            <div class="flex justify-between text-sm mb-8" style="padding:4px 0;border-bottom:1px solid var(--border)">
              <span style="text-transform:capitalize;font-weight:500">${escHtml(sec)}</span>
              <span class="${conf > 0 ? 'badge-success' : 'badge badge-muted'}" style="${conf>0?'':''}font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px">
                ${conf > 0 ? Math.round(conf*100)+'%' : 'Not found'}
              </span>
            </div>`).join('')}
        </div>

        <div class="card">
          <div class="card-header"><h2>Projects Detected</h2></div>
          ${(profile.projects||[]).slice(0,5).map(p=>`<p class="text-sm" style="margin-bottom:6px">💡 ${escHtml(p.raw||p)}</p>`).join('')
          || '<p class="text-sm text-muted">None detected</p>'}
        </div>

        <button class="btn btn-primary btn-block btn-lg" id="confirm-btn" style="margin-top:4px">
          ✓ Confirm Profile & View Matches
        </button>
      </div>
    </div>`));
  attachLogout();

  window.removeSkill = function(i) {
    skillsState.splice(i, 1);
    document.getElementById('skills-container').innerHTML = renderSkillTags();
    document.getElementById('skill-count').textContent = skillsState.length;
  };

  const skillsRes = await API.listSkills();
  const sel = document.getElementById('skill-select');
  if (skillsRes.ok) {
    const byCategory = {};
    (skillsRes.data.skills||[]).forEach(s => {
      const cat = s.category || 'Other';
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(s);
    });
    Object.entries(byCategory).forEach(([cat, skills]) => {
      const og = document.createElement('optgroup'); og.label = cat;
      skills.forEach(s => { const o = document.createElement('option'); o.value = s.skill_id; o.textContent = s.canonical_name; og.appendChild(o); });
      sel.appendChild(og);
    });
  }

  document.getElementById('add-skill-btn').addEventListener('click', () => {
    const sid = parseInt(sel.value);
    if (!sid) return;
    const sname = sel.options[sel.selectedIndex]?.text;
    if (!sname || skillsState.find(s=>s.skill_id===sid)) return;
    skillsState.push({ skill_id: sid, canonical_name: sname, confidence: 0.60, source: 'self_reported', section: 'other' });
    document.getElementById('skills-container').innerHTML = renderSkillTags();
    document.getElementById('skill-count').textContent = skillsState.length;
    sel.value = '';
  });

  document.getElementById('confirm-btn').addEventListener('click', async () => {
    const btn = document.getElementById('confirm-btn');
    btn.textContent = 'Confirming…'; btn.disabled = true;
    await API.editProfile(resumeId, { skills: skillsState.map(s=>({...s, action:'update'})) });
    const r = await API.confirmProfile(resumeId);
    if (r.ok) navigate('/matches');
    else { btn.textContent = '✓ Confirm Profile & View Matches'; btn.disabled = false;
           showAlert(document.getElementById('review-alerts'), 'danger', r.error?.message || 'Confirmation failed.'); }
  });
});

/* ═══════════════════════════════════════════════════════════════════════════
   CAREER MATCHES
═══════════════════════════════════════════════════════════════════════════ */
route('/matches', async () => {
  if (!await checkAuth()) return;
  mount(loadingShell('Analyzing your profile…'));
  attachLogout();

  const res = await API.getRecommendations(false);

  if (!res.ok || res.error) {
    mount(appShell(`<div class="alert alert-warn">${res.error?.message||'Could not load recommendations.'}<br/>
      <a href="/upload" data-nav="/upload" class="btn btn-primary btn-sm mt-8">Upload Resume</a></div>`));
    attachLogout(); return;
  }
  if (res.data.abstained) {
    mount(appShell(`
      <div class="empty-state" style="padding:60px 24px">
        <div class="es-icon">🔭</div>
        <h3>More information needed</h3>
        <p>${escHtml(res.data.reason)}</p>
        <a href="/upload" data-nav="/upload" class="btn btn-primary">Upload Resume</a>
      </div>`));
    attachLogout(); return;
  }

  const recs = res.data.recommendations || [];

  mount(appShell(`
    <div class="page-header">
      <div class="page-title">Career Matches</div>
      <div class="page-sub">Ranked by how well your confirmed skills match each role's requirements.</div>
    </div>
    <div class="alert alert-info" style="font-size:12px">
      Match bands are based on your confirmed skills vs the role knowledge base. These are guidance indicators — not predictions of employment.
    </div>
    <div id="match-alerts"></div>
    ${recs.map((r, i) => `
      <div class="role-card" id="role-card-${r.role_id}">
        <div class="role-header">
          <div style="flex:1">
            <div class="role-rank">#${i+1}</div>
            <div class="role-name">${escHtml(r.role_name)}</div>
            <div class="role-desc">${escHtml(r.description||'')}</div>
          </div>
          <div style="text-align:right;flex-shrink:0">${bandBadge(r.band)}</div>
        </div>
        <div class="score-bar">
          <div class="score-label">
            <span>Role coverage</span>
            <span>${Math.round((r.kb_score||0)*100)}%</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:${Math.round((r.kb_score||0)*100)}%"></div></div>
        </div>
        <div class="role-footer">
          <button class="btn btn-primary btn-sm" onclick="selectTarget(${r.role_id},'${escHtml(r.role_name)}')">Set as Target</button>
          <button class="btn btn-secondary btn-sm" onclick="toggleExp(${r.role_id})">View Evidence ▾</button>
          <div class="feedback-row" style="margin:0">
            <span class="fb-label">Helpful?</span>
            <button class="feedback-btn" onclick="sendFb(${r.role_id},1,this)">👍</button>
            <button class="feedback-btn" onclick="sendFb(${r.role_id},-1,this)">👎</button>
          </div>
        </div>
        <div class="hidden" id="exp-${r.role_id}">
          <hr class="divider"/>
          <div class="grid-2" style="gap:16px">
            <div>
              <p class="text-xs text-muted font-bold mb-8">✅ MATCHED SKILLS (${r.explanation?.matched_skills?.length||0})</p>
              <div>${(r.explanation?.matched_skills||[]).map(s=>`
                <span class="skill-tag">
                  <span class="conf-dot ${s.confidence>=.7?'conf-strong':s.confidence>=.4?'conf-partial':'conf-gap'}"></span>
                  ${escHtml(s.canonical_name)}
                  <span class="badge badge-muted" style="font-size:10px">${s.importance}</span>
                </span>`).join('')||'<span class="text-muted text-xs">None matched</span>'}
              </div>
            </div>
            <div>
              <p class="text-xs text-muted font-bold mb-8">❌ MISSING CORE SKILLS (${r.explanation?.missing_core?.length||0})</p>
              <div>${(r.explanation?.missing_core||[]).map(s=>`
                <span class="skill-tag"><span class="conf-dot conf-gap"></span>${escHtml(s.canonical_name)}</span>`).join('')
              ||'<span class="text-xs" style="color:var(--success)">✓ All core skills covered!</span>'}
              </div>
            </div>
          </div>
          <p class="limitation-note">${escHtml(r.explanation?.limitation_note||'')}</p>
        </div>
      </div>`).join('')}`));
  attachLogout();

  window.toggleExp    = id => document.getElementById(`exp-${id}`).classList.toggle('hidden');
  window.selectTarget = async (roleId, roleName) => {
    const btn = document.querySelector(`#role-card-${roleId} .btn-primary`);
    btn.textContent = 'Setting…'; btn.disabled = true;
    const r = await API.setTarget(roleId);
    if (r.ok) {
      showAlert(document.getElementById('match-alerts'), 'success', `${roleName} set as target! Gaps and roadmap computed.`);
      btn.textContent = '✓ Target Set';
    } else { btn.textContent = 'Set as Target'; btn.disabled = false; }
  };
  window.sendFb = async (id, rating, el) => {
    el.classList.add(rating===1?'active-up':'active-down');
    await API.sendFeedback({ target_type:'recommendation', target_id:id, rating });
  };
});

/* ═══════════════════════════════════════════════════════════════════════════
   SKILL GAP
═══════════════════════════════════════════════════════════════════════════ */
route('/gap', async () => {
  if (!await checkAuth()) return;
  mount(loadingShell());
  attachLogout();

  const [gapRes, profileRes] = await Promise.all([API.getGaps(), API.getProfile()]);
  if (!gapRes.ok) {
    mount(appShell(`<div class="alert alert-warn">${gapRes.error?.message||'No gap analysis.'}<br/>
      <a href="/matches" data-nav="/matches" class="btn btn-primary btn-sm mt-8">Select a Target Role</a></div>`));
    attachLogout(); return;
  }

  const gaps = gapRes.data.gaps || [];
  const readiness = gapRes.data.readiness;
  const target = profileRes.data?.profile?.target_role;
  const sum = { strong:0, partial:0, gap:0 };
  gaps.forEach(g => { sum[g.status] = (sum[g.status]||0)+1; });

  const byPriority = { high:[], medium:[], low:[] };
  gaps.forEach(g => byPriority[g.priority||'low']?.push(g));

  const pct = readiness != null ? Math.round(readiness*100) : 0;

  mount(appShell(`
    <div class="page-header-row">
      <div>
        <div class="page-title">Skill Gap Analysis</div>
        <div class="page-sub">Target: <strong>${target ? escHtml(target.name) : 'Not set'}</strong></div>
      </div>
      <a href="/roadmap" data-nav="/roadmap" class="btn btn-primary btn-sm">View Roadmap →</a>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon si-blue">📊</div>
        <div class="stat-label">Career Readiness</div>
        <div class="stat-value">${pct}<span style="font-size:14px;font-weight:500">%</span></div>
        <div class="stat-sub">Profile-match indicator</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon si-green">✅</div>
        <div class="stat-label">Strong Skills</div>
        <div class="stat-value" style="color:var(--success)">${sum.strong}</div>
        <div class="stat-sub">Confidence ≥ 70%</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon si-orange">🟡</div>
        <div class="stat-label">Improving</div>
        <div class="stat-value" style="color:var(--warn)">${sum.partial}</div>
        <div class="stat-sub">40–70% confidence</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background:var(--danger-bg)">❌</div>
        <div class="stat-label">Gaps</div>
        <div class="stat-value" style="color:var(--danger)">${sum.gap}</div>
        <div class="stat-sub">Below 40%</div>
      </div>
    </div>

    <div class="card" style="margin-bottom:20px">
      <div class="flex justify-between mb-8">
        <span style="font-size:13px;font-weight:600">Overall Readiness</span>
        <span style="font-size:13px;font-weight:700;color:${pct>=70?'var(--success)':pct>=40?'var(--warn)':'var(--danger)'}">${pct}%</span>
      </div>
      <div class="progress-bar"><div class="progress-fill ${pct>=70?'green':pct>=40?'orange':''}" style="width:${pct}%"></div></div>
      <p class="text-xs text-muted mt-8">This is a profile-match indicator — not a measure of employability.</p>
    </div>

    ${['high','medium','low'].filter(p=>byPriority[p].length).map(p=>`
      <div class="card">
        <div class="card-header">
          <h2>${p.charAt(0).toUpperCase()+p.slice(1)} Priority ${priorityBadge(p)}</h2>
        </div>
        <table class="gap-table">
          <thead><tr>
            <th>Skill</th><th>Category</th><th>Status</th><th>Importance</th>
          </tr></thead>
          <tbody>
            ${byPriority[p].map(g=>`
              <tr>
                <td style="font-weight:600">${escHtml(g.skill_name)}</td>
                <td style="color:var(--muted)">${escHtml(g.category||'')}</td>
                <td>${statusBadge(g.status)}</td>
                <td><span class="badge badge-muted" style="font-size:11px">${g.importance||'—'}</span></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`).join('')}`));
  attachLogout();
});

/* ═══════════════════════════════════════════════════════════════════════════
   ROADMAP
═══════════════════════════════════════════════════════════════════════════ */
route('/roadmap', async () => {
  if (!await checkAuth()) return;
  mount(loadingShell());
  attachLogout();

  const [roadmapRes, profileRes] = await Promise.all([API.getRoadmap(), API.getProfile()]);

  if (!roadmapRes.ok || !roadmapRes.data.items?.length) {
    mount(appShell(`
      <div class="empty-state" style="padding:60px">
        <div class="es-icon">🗺️</div>
        <h3>No roadmap yet</h3>
        <p>${roadmapRes.error?.message||'Select a target role to generate your learning roadmap.'}</p>
        <a href="/matches" data-nav="/matches" class="btn btn-primary">Select Target Role</a>
      </div>`));
    attachLogout(); return;
  }

  const items  = roadmapRes.data.items || [];
  const total  = roadmapRes.data.total  || items.length;
  const done   = roadmapRes.data.completed || 0;
  const pct    = roadmapRes.data.progress_pct || (total ? Math.round(done/total*100) : 0);
  const target = profileRes.data?.profile?.target_role;

  const stages = {};
  items.forEach(item => { if (!stages[item.stage]) stages[item.stage] = []; stages[item.stage].push(item); });

  const stageIcons = { Fundamentals:'📚', Tools:'🛠️', Practice:'🔬', Portfolio:'💼', 'Job Readiness':'🚀' };

  mount(appShell(`
    <div class="page-header-row">
      <div>
        <div class="page-title">Learning Roadmap</div>
        <div class="page-sub">Target: <strong>${target ? escHtml(target.name) : '—'}</strong></div>
      </div>
      <a href="/gap" data-nav="/gap" class="btn btn-secondary btn-sm">📊 View Gaps</a>
    </div>

    <div class="card card-flat" style="margin-bottom:24px">
      <div class="flex justify-between mb-8">
        <span style="font-size:13px;font-weight:600">${done} of ${total} items completed</span>
        <span style="font-size:15px;font-weight:800;color:var(--accent)">${pct}%</span>
      </div>
      <div class="progress-bar" style="height:10px"><div class="progress-fill green" style="width:${pct}%"></div></div>
    </div>

    ${Object.entries(stages).map(([stage, stageItems]) => `
      <div style="margin-bottom:24px">
        <div class="roadmap-stage-header">
          <div class="roadmap-stage-icon">${stageIcons[stage]||'📌'}</div>
          <div>
            <div class="roadmap-stage-title">${escHtml(stage)}</div>
            <div class="roadmap-stage-count">${stageItems.length} item${stageItems.length!==1?'s':''}</div>
          </div>
        </div>
        ${stageItems.map(item => `
          <div class="roadmap-item ${item.status}" id="ritem-${item.id}">
            <div class="roadmap-num">${item.status==='completed'?'✓':item.order}</div>
            <div class="roadmap-info">
              <div class="roadmap-skill">${escHtml(item.skill_name||'')}</div>
              <div class="roadmap-meta">
                <span>~${item.est_hours}h estimated</span>
                <span style="text-transform:capitalize">${item.status.replace('_',' ')}</span>
              </div>
            </div>
            <div class="roadmap-actions">
              ${item.status!=='completed'
                ? `<button class="btn btn-success btn-sm" onclick="markItem(${item.id},'completed')">✓ Done</button>
                   ${item.status!=='in_progress'?`<button class="btn btn-secondary btn-sm" onclick="markItem(${item.id},'in_progress')">▶ Start</button>`:''}`
                : `<span class="badge badge-success">Completed</span>`}
            </div>
          </div>`).join('')}
      </div>`).join('')}`));
  attachLogout();

  window.markItem = async (id, st) => { if ((await API.updateItem(id, st)).ok) navigate('/roadmap'); };
});

/* ═══════════════════════════════════════════════════════════════════════════
   AI COPILOT
═══════════════════════════════════════════════════════════════════════════ */
function renderMarkdownMsg(text) {
  return String(text||'')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/^[•\-]\s+(.+)$/gm,'<li>$1</li>')
    .replace(/^(\d+)\.\s+(.+)$/gm,'<li>$2</li>')
    .replace(/(<li>[\s\S]*?<\/li>)+/g, m=>`<ul style="padding-left:18px;margin:6px 0">${m}</ul>`)
    .replace(/\n/g,'<br>');
}

route('/copilot', async () => {
  if (!await checkAuth()) return;

  mount(appShell(`
    <div class="page-header">
      <div class="page-title">🤖 AI Career Copilot</div>
      <div class="page-sub">Ask me anything about your career, gaps, roadmap, or interview prep.</div>
    </div>
    <div class="chat-wrapper">
      <div id="chat-suggestions" class="chat-suggestions"></div>
      <div class="chat-messages" id="chat-messages">
        <div class="chat-row">
          <div class="chat-avatar bot">🤖</div>
          <div>
            <div class="chat-bubble assistant">
              👋 Hi! I'm your <strong>AI Career Copilot</strong>.<br/>
              I can help with career matches, skill gaps, roadmap, resume tips, interview prep, and project ideas.<br/>
              <span style="font-size:12px;color:var(--muted)">Try a suggested prompt below or ask anything.</span>
            </div>
          </div>
        </div>
      </div>
      <div class="chat-input-bar">
        <textarea id="chat-input" placeholder="Ask anything… (Enter to send)" rows="1"></textarea>
        <button class="send-btn" id="chat-send" title="Send">➤</button>
      </div>
    </div>
    <div id="intent-display" style="text-align:right;margin-top:6px"></div>`));
  attachLogout();

  const messagesEl = document.getElementById('chat-messages');
  const inputEl    = document.getElementById('chat-input');
  const sendBtn    = document.getElementById('chat-send');
  const suggestEl  = document.getElementById('chat-suggestions');
  const intentEl   = document.getElementById('intent-display');

  // Auto-resize textarea
  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  });

  function addBubble(role, content) {
    const row = document.createElement('div');
    row.className = `chat-row ${role}`;
    const avatar = document.createElement('div');
    avatar.className = `chat-avatar ${role==='user'?'user':'bot'}`;
    avatar.textContent = role==='user' ? initials(State.user?.name) : '🤖';
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;
    bubble.innerHTML = renderMarkdownMsg(content);
    row.appendChild(avatar);
    const wrap = document.createElement('div');
    wrap.appendChild(bubble);
    row.appendChild(wrap);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showTyping() {
    const row = document.createElement('div');
    row.className = 'chat-row'; row.id = 'typing-row';
    row.innerHTML = `<div class="chat-avatar bot">🤖</div>
      <div><div class="chat-bubble assistant chat-typing-row">
        <div class="chat-typing-dots"><span></span><span></span><span></span></div>
        <span style="font-size:12px;color:var(--muted)">Thinking…</span>
      </div></div>`;
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
  function hideTyping() { document.getElementById('typing-row')?.remove(); }

  async function send() {
    const msg = inputEl.value.trim();
    if (!msg) return;
    inputEl.value = ''; inputEl.style.height = 'auto';
    sendBtn.disabled = true; inputEl.disabled = true;
    addBubble('user', msg);
    showTyping();
    const res = await API.sendMessage(msg, State.chatSessionId);
    hideTyping();
    sendBtn.disabled = false; inputEl.disabled = false; inputEl.focus();
    if (res.ok) {
      State.chatSessionId = res.data.session_id;
      addBubble('assistant', res.data.response);
      if (res.data.intent && res.data.intent !== 'out_of_scope') {
        const lbl = res.data.intent.replace(/_/g,' ');
        const conf = Math.round((res.data.intent_confidence||0)*100);
        intentEl.innerHTML = `<span class="intent-tag">🧠 ${lbl} · ${conf}%</span>`;
      } else intentEl.innerHTML = '';
    } else addBubble('assistant', '⚠️ Something went wrong. Please try again.');
  }

  sendBtn.addEventListener('click', send);
  inputEl.addEventListener('keydown', e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send(); } });

  // Dynamic suggested prompts based on profile
  const profileRes = await API.getProfile();
  const target = profileRes.data?.profile?.target_role?.name;
  const chips = target ? [
    `What skills am I missing for ${target}?`,
    `What should I learn next?`,
    `Prepare me for a ${target} interview`,
    `Suggest portfolio projects`,
  ] : ['Which career suits me best?', 'What skills am I missing?', 'Show my roadmap', 'Give me project ideas'];

  chips.forEach(c => {
    const chip = document.createElement('button');
    chip.className = 'suggest-chip'; chip.textContent = c;
    chip.onclick = () => { inputEl.value = c; send(); };
    suggestEl.appendChild(chip);
  });
});

/* ═══════════════════════════════════════════════════════════════════════════
   RESUME BUILDER
═══════════════════════════════════════════════════════════════════════════ */
route('/builder', async () => {
  if (!await checkAuth()) return;
  mount(loadingShell());
  attachLogout();

  const [profileRes, skillsRes] = await Promise.all([API.getProfile(), API.getUserSkills()]);
  const u = profileRes.data?.user || State.user;
  const userSkills = (skillsRes.data?.skills||[]).filter(s=>s.confidence>=0.4).map(s=>s.canonical_name);

  mount(appShell(`
    <div class="page-header">
      <div class="page-title">📝 Resume Builder</div>
      <div class="page-sub">Generate a professional ATS-friendly PDF from your profile.</div>
    </div>
    <div id="builder-alerts"></div>
    <div class="grid-2">
      <div>
        <div class="card">
          <div class="card-header"><h2>Choose Template</h2></div>
          ${[
            [1,'📋','Minimal ATS','Clean, single-column, optimized for ATS systems'],
            [2,'🎓','Student / Fresher','Projects and education front and center'],
            [3,'💻','Technical','Skills-forward with tech stack highlight'],
          ].map(([id, icon, name, desc]) => `
            <div class="role-card" id="tmpl-${id}" onclick="selTmpl(${id})" style="margin-bottom:10px">
              <div class="role-header">
                <div>
                  <div style="font-size:20px;margin-bottom:4px">${icon}</div>
                  <div class="role-name">${name}</div>
                  <div class="role-desc">${desc}</div>
                </div>
              </div>
            </div>`).join('')}
          <input type="hidden" id="sel-tmpl" value="1" />
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h2>Your Details</h2></div>
        <div class="form-group"><label>Full Name</label><input class="form-control" id="r-name" value="${escHtml(u?.name||'')}" /></div>
        <div class="form-group"><label>Email</label><input class="form-control" id="r-email" value="${escHtml(u?.email||'')}" /></div>
        <div class="form-group"><label>Phone</label><input class="form-control" id="r-phone" placeholder="+1 555 000 0000" /></div>
        <div class="form-group"><label>Location</label><input class="form-control" id="r-location" placeholder="City, Country" /></div>
        <div class="form-group"><label>Professional Summary</label><textarea class="form-control" id="r-summary" rows="3" placeholder="2–3 sentence overview of your background and goals."></textarea></div>
        <div class="form-group">
          <label>Skills (comma-separated)</label>
          <input class="form-control" id="r-skills" value="${escHtml(userSkills.join(', '))}" />
          <div class="form-hint">Pre-filled from your confirmed skills</div>
        </div>
        <div class="form-group"><label>Certifications (one per line)</label><textarea class="form-control" id="r-certs" rows="2" placeholder="AWS Certified, Google Analytics…"></textarea></div>
        <button class="btn btn-primary btn-block" id="gen-btn" style="margin-top:4px">⬇ Generate PDF Resume</button>
      </div>
    </div>`));
  attachLogout();

  window.selTmpl = id => {
    [1,2,3].forEach(i => document.getElementById(`tmpl-${i}`)?.classList.remove('selected'));
    document.getElementById(`tmpl-${id}`)?.classList.add('selected');
    document.getElementById('sel-tmpl').value = id;
  };
  window.selTmpl(1);

  document.getElementById('gen-btn').addEventListener('click', async () => {
    const btn = document.getElementById('gen-btn');
    btn.textContent = '⏳ Generating…'; btn.disabled = true;
    const skills = document.getElementById('r-skills').value.split(',').map(s=>s.trim()).filter(Boolean);
    const certs  = document.getElementById('r-certs').value.split('\n').map(s=>s.trim()).filter(Boolean);
    const res = await API.generateResume({
      template_id: parseInt(document.getElementById('sel-tmpl').value),
      resume_data: {
        name: document.getElementById('r-name').value,
        email: document.getElementById('r-email').value,
        phone: document.getElementById('r-phone').value,
        location: document.getElementById('r-location').value,
        summary: document.getElementById('r-summary').value,
        skills, certifications: certs,
      }
    });
    btn.textContent = '⬇ Generate PDF Resume'; btn.disabled = false;
    const alerts = document.getElementById('builder-alerts');
    if (res.ok) {
      const genId = res.data.generated_resume_id;
      alerts.innerHTML = `<div class="alert alert-success">Resume generated! <a href="/api/resume-builder/download/${genId}" target="_blank" class="btn btn-success btn-sm" style="margin-left:8px">⬇ Download PDF</a></div>`;
    } else showAlert(alerts, 'danger', res.error?.message || 'Generation failed.');
  });
});

/* ═══════════════════════════════════════════════════════════════════════════
   INTERVIEW PREP
═══════════════════════════════════════════════════════════════════════════ */
route('/interview', async () => {
  if (!await checkAuth()) return;
  mount(loadingShell());
  attachLogout();

  const profileRes = await API.getProfile();
  const target = profileRes.data?.profile?.target_role;

  if (!target) {
    mount(appShell(`<div class="empty-state"><div class="es-icon">🎤</div><h3>Select a target role first</h3>
      <p>Choose your target role on the Career Matches page to get role-specific interview questions.</p>
      <a href="/matches" data-nav="/matches" class="btn btn-primary">Go to Matches</a></div>`));
    attachLogout(); return;
  }

  const topics  = target.interview_topics || [];
  const projects = target.typical_projects || [];
  const qMap = {
    'Python OOP':            ['What is the difference between class and instance methods?','Explain Python\u2019s MRO (method resolution order).'],
    'Flask/Django architecture':['How does Flask handle request routing?','What is Django\u2019s ORM and how does it work?'],
    'REST API design':       ['What are the six REST constraints?','How do you handle API versioning?'],
    'Database design':       ['When would you denormalize a database schema?','What indexes would you add to this high-read table?'],
    'Authentication':        ['How does JWT differ from session-based auth?','What is OAuth 2.0 and when would you use it?'],
    'Testing':               ['What is the difference between unit, integration and E2E tests?','How do you test a Flask API endpoint?'],
    'System design':         ['How would you design a URL shortener at scale?','Explain the CAP theorem with an example.'],
    'SQL':                   ['Write a query to find the second-highest salary.','How do you optimize a slow JOIN query?'],
    'Machine learning':      ['Explain the bias-variance tradeoff.','How do you handle class imbalance in a dataset?'],
    'Docker':                ['What is the difference between a Dockerfile and docker-compose?','How do you manage secrets in containers?'],
  };
  const questions = topics.flatMap(t => qMap[t] || [`Describe your approach to ${t}.`, `Give an example of ${t} in a project.`]).slice(0, 12);

  mount(appShell(`
    <div class="page-header">
      <div class="page-title">🎤 Interview Preparation</div>
      <div class="page-sub">Role: <strong>${escHtml(target.name)}</strong></div>
    </div>

    <div class="grid-2">
      <div>
        <div class="card">
          <div class="card-header"><h2>Key Topics to Study</h2></div>
          <div style="display:flex;flex-wrap:wrap;gap:8px">
            ${topics.map(t=>`<span class="badge badge-info" style="font-size:12px;padding:5px 12px">${escHtml(t)}</span>`).join('')}
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h2>Typical Portfolio Projects</h2></div>
          <ul style="padding-left:18px">
            ${projects.map(p=>`<li style="margin-bottom:8px;font-size:13px">${escHtml(p)}</li>`).join('')}
          </ul>
        </div>
        <div class="card" style="background:var(--accent-lt);border-color:var(--accent)">
          <div class="card-header"><h2>Interview Tips</h2></div>
          <ul style="padding-left:18px;font-size:13px;display:flex;flex-direction:column;gap:8px">
            <li>Use the <strong>STAR method</strong> for behavioural questions</li>
            <li>Walk through a real project that shows each core skill</li>
            <li>Explain your <em>thinking</em>, not just your answer</li>
            <li>Ask clarifying questions before solving system design problems</li>
          </ul>
        </div>
      </div>
      <div>
        <div class="card">
          <div class="card-header"><h2>Practice Questions <span class="badge badge-muted">${questions.length}</span></h2></div>
          ${questions.map((q, i) => `
            <div class="interview-q" onclick="this.classList.toggle('open')">
              <div class="q-num">Q${i+1}</div>
              <div class="q-text">
                ${escHtml(q)}
                <span class="q-arrow">›</span>
              </div>
              <div class="q-hint">💡 Think about a real example from your projects. Use STAR: Situation → Task → Action → Result.</div>
            </div>`).join('')}
        </div>
        <div class="alert alert-info text-sm">
          Ask the AI Copilot to coach you through any of these questions.
          <a href="/copilot" data-nav="/copilot" class="btn btn-sm btn-ghost" style="margin-left:8px">Open Copilot</a>
        </div>
      </div>
    </div>`));
  attachLogout();
});

/* ═══════════════════════════════════════════════════════════════════════════
   PROFILE
═══════════════════════════════════════════════════════════════════════════ */
route('/profile', async () => {
  if (!await checkAuth()) return;
  mount(loadingShell());
  attachLogout();

  const profileRes = await API.getProfile();
  const user    = profileRes.data?.user || State.user;
  const profile = profileRes.data?.profile || {};

  mount(appShell(`
    <div class="page-header">
      <div class="page-title">Profile & Settings</div>
      <div class="page-sub">Manage your account details and career goals.</div>
    </div>
    <div id="profile-alerts"></div>
    <div class="grid-2">
      <div>
        <div class="card">
          <div class="card-header"><h2>Account Details</h2></div>
          <form id="profile-form">
            <div class="form-group"><label>Full Name</label><input class="form-control" id="p-name" value="${escHtml(user?.name||'')}" /></div>
            <div class="form-group"><label>Email</label><input class="form-control" value="${escHtml(user?.email||'')}" disabled /></div>
            <div class="form-group"><label>Education Summary</label><textarea class="form-control" id="p-edu" rows="3">${escHtml(profile.education_summary||'')}</textarea></div>
            <div class="form-group"><label>Career Goals</label><textarea class="form-control" id="p-goals" rows="3" placeholder="e.g. Become a backend developer in 6 months">${escHtml(profile.goals||'')}</textarea></div>
            <button type="submit" class="btn btn-primary">Save Changes</button>
          </form>
        </div>
      </div>
      <div>
        <div class="card">
          <div class="card-header"><h2>Current Target</h2></div>
          ${profile.target_role
            ? `<div style="display:flex;align-items:center;gap:10px">
                <div style="font-size:24px">🎯</div>
                <div><div style="font-weight:700">${escHtml(profile.target_role.name)}</div>
                <div class="text-sm text-muted">Currently targeting</div></div>
              </div>`
            : `<p class="text-sm text-muted">Not set</p>`}
          <a href="/matches" data-nav="/matches" class="btn btn-ghost btn-sm mt-12">Change Target</a>
        </div>
        <div class="card">
          <div class="card-header"><h2>Quick Links</h2></div>
          <div style="display:flex;flex-direction:column;gap:8px">
            <a href="/gap"       data-nav="/gap"       class="btn btn-secondary" style="justify-content:flex-start">📊 Skill Gap Analysis</a>
            <a href="/interview" data-nav="/interview" class="btn btn-secondary" style="justify-content:flex-start">🎤 Interview Preparation</a>
            <a href="/builder"   data-nav="/builder"   class="btn btn-secondary" style="justify-content:flex-start">📝 Resume Builder</a>
          </div>
        </div>
        <div class="card" style="border-color:var(--danger-bd);background:var(--danger-bg)">
          <div class="card-header"><h2 style="color:var(--danger)">⚠️ Danger Zone</h2></div>
          <p class="text-sm text-muted mb-8">This will permanently delete your account and all data.</p>
          <button class="btn btn-danger btn-sm" id="del-btn">Delete My Account</button>
        </div>
      </div>
    </div>`));
  attachLogout();

  document.getElementById('profile-form').addEventListener('submit', async e => {
    e.preventDefault();
    const r = await API.updateProfile({ name: document.getElementById('p-name').value, education_summary: document.getElementById('p-edu').value, goals: document.getElementById('p-goals').value });
    showAlert(document.getElementById('profile-alerts'), r.ok ? 'success' : 'danger', r.ok ? 'Profile updated!' : r.error?.message || 'Update failed.');
  });
  document.getElementById('del-btn').addEventListener('click', async () => {
    if (!confirm('Delete your account permanently?')) return;
    await fetch('/api/auth/account', { method:'DELETE', credentials:'include' });
    State.user = null; navigate('/');
  });
});

/* ═══════════════════════════════════════════════════════════════════════════
   NOT FOUND
═══════════════════════════════════════════════════════════════════════════ */
route('*', async () => {
  await checkAuth();
  const shell = State.user ? (c => mount(appShell(c))) : (c => mount(publicTopbar()+`<div style="padding:80px 24px">${c}</div>`));
  shell(`<div class="empty-state"><div class="es-icon">🔭</div><h3>Page not found</h3>
    <p>The page you're looking for doesn't exist.</p>
    <a href="/" data-nav="/" class="btn btn-primary">Go Home</a></div>`);
  if (State.user) attachLogout();
});

/* ── Shared helpers ───────────────────────────────────────────────────────── */
function attachLogout() {
  document.getElementById('logout-btn')?.addEventListener('click', async () => {
    await API.logout(); State.user = null; navigate('/');
  });
}

/* ── Boot ─────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', render);
