/**
 * api.js – All fetch calls to the CareerBridge AI backend.
 * Every call returns {ok, data, error}.
 */
const API = (() => {
  async function call(method, path, body = null, opts = {}) {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    };
    if (body && !(body instanceof FormData)) {
      options.body = JSON.stringify(body);
    } else if (body instanceof FormData) {
      delete options.headers['Content-Type'];
      options.body = body;
    }
    try {
      const res = await fetch(path, options);
      const json = await res.json().catch(() => ({}));
      return { ok: res.ok, status: res.status, data: json.data || {}, error: json.error || null, raw: json };
    } catch (e) {
      return { ok: false, status: 0, data: {}, error: { code: 'NETWORK_ERROR', message: e.message }, raw: {} };
    }
  }

  return {
    // Auth
    register: (d)    => call('POST', '/api/auth/register', d),
    login:    (d)    => call('POST', '/api/auth/login', d),
    logout:   ()     => call('POST', '/api/auth/logout'),
    me:       ()     => call('GET',  '/api/auth/me'),

    // Resume
    uploadResume:   (fd)  => call('POST', '/api/resume/upload', fd),
    listResumes:    ()    => call('GET',  '/api/resume'),
    getResume:      (id)  => call('GET',  `/api/resume/${id}`),
    deleteResume:   (id)  => call('DELETE', `/api/resume/${id}`),
    editProfile:    (id, d) => call('PATCH', `/api/resume/${id}/profile`, d),
    confirmProfile: (id)  => call('POST', `/api/resume/${id}/confirm`),

    // Careers
    getRecommendations: (refresh) => call('GET', `/api/careers/recommendations${refresh ? '?refresh=true' : ''}`),
    getRoleDetail:      (id)  => call('GET', `/api/careers/${id}`),
    compareRoles:       (a,b) => call('GET', `/api/careers/compare?a=${a}&b=${b}`),
    setTarget:          (rid) => call('POST', '/api/careers/target', { role_id: rid }),

    // Skills
    listSkills:   ()   => call('GET',  '/api/skills'),
    getGaps:      ()   => call('GET',  '/api/skills/gaps'),
    getUserSkills:()   => call('GET',  '/api/skills/user'),
    addSkill:     (sid)=> call('POST', '/api/skills/user', { skill_id: sid }),

    // Roadmap
    getRoadmap:   ()        => call('GET', '/api/roadmap'),
    updateItem:   (id, st)  => call('PATCH', `/api/roadmap/items/${id}`, { status: st }),
    getProgress:  ()        => call('GET', '/api/roadmap/progress'),

    // Chat
    sendMessage: (msg, sid) => call('POST', '/api/chat/message', { message: msg, session_id: sid }),
    getChatHistory: (sid)   => call('GET', `/api/chat/history${sid ? '?session_id='+sid : ''}`),

    // Profile
    getProfile:    ()  => call('GET',   '/api/profile'),
    updateProfile: (d) => call('PATCH', '/api/profile', d),

    // Resume Builder
    listTemplates: ()   => call('GET', '/api/resume-builder/templates'),
    generateResume: (d) => call('POST', '/api/resume-builder/generate', d),
    suggestText:    (d) => call('POST', '/api/resume-builder/suggest', d),

    // Feedback
    sendFeedback: (d) => call('POST', '/api/feedback', d),

    // Health
    health: () => call('GET', '/api/health'),
  };
})();
