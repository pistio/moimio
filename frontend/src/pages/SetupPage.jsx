import { useState } from 'react';
import { setup as setupApi } from '../services/api';
import { useI18n, SUPPORTED_LANGS } from '../hooks/useI18n';
import Wordmark from '../components/Wordmark';
import ThemeToggle from '../components/ThemeToggle';
import TranslatedError from '../components/TranslatedError';

// v0.59a-1: same auto-derivation pattern as AdminLayout sidebar.
// See vite.config.js `define` for the build-time source of truth
// (frontend/package.json::moimioVersion). Fallback 'dev' for tests.
const MOIMIO_VERSION = typeof __MOIMIO_VERSION__ !== 'undefined' ? __MOIMIO_VERSION__ : 'dev';

export default function SetupPage({ onComplete }) {
  const [bootstrap] = useState(() => {
    const match = /^#bootstrap=([A-Za-z0-9_-]{32,128})$/.exec(location.hash);
    if (match) history.replaceState(null, '', location.pathname);
    return match?.[1];
  });
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirm: '' });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const { t, lang, setLang } = useI18n();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (form.password !== form.confirm) { setError(t('reset.error.mismatch')); return; }
    if (form.password.length < 8) { setError(t('reset.error.short')); return; }
    setLoading(true);
    try {
      await setupApi.init({ email: form.email, full_name: form.full_name, password: form.password, ...(bootstrap ? { bootstrap_token: bootstrap } : {}) });
      onComplete();
    } catch (err) { setError(err); }
    finally { setLoading(false); }
  };

  const inputClass = "w-full rounded-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-steel-blue " +
                     "bg-white dark:bg-white/5 border border-card " +
                     "text-body";

  return (
    <div className="min-h-screen flex items-center justify-center p-4"
         style={{ backgroundColor: 'var(--app-bg)' }}>
      <div className="fixed top-[calc(0.75rem+env(safe-area-inset-top))] right-[calc(0.75rem+env(safe-area-inset-right))]">
        <ThemeToggle tone="inline" />
      </div>

      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <img src="/logogram.svg" alt="Moimio" className="w-16 h-16 mx-auto mb-4" />
          <Wordmark size="lg" />
          <p className="text-xs uppercase tracking-caps mt-2"
             style={{ color: 'var(--text-subtle)' }}>{t('setup.title')}</p>
        </div>

        <div className="card-surface-solid p-6">
          <h2 className="font-heading font-bold text-lg mb-1"
              style={{ color: 'var(--text-primary)' }}>
            {t('setup.submit')}
          </h2>
          <p className="text-xs mb-5" style={{ color: 'var(--text-subtle)' }}>
            {t('setup.subtitle')}
          </p>

          <TranslatedError err={error} className="text-xs rounded-card p-2 mb-4" />

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold mb-1"
                     style={{ color: 'var(--text-muted)' }}>{t('setup.full_name')}</label>
              <input type="text" value={form.full_name}
                     onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))}
                     required autoFocus className={inputClass} />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1"
                     style={{ color: 'var(--text-muted)' }}>{t('setup.email')}</label>
              <input type="email" value={form.email}
                     onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
                     required className={inputClass} />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1"
                     style={{ color: 'var(--text-muted)' }}>{t('setup.password')}</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} value={form.password}
                       onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                       required className={`${inputClass} pr-16`} />
                <button type="button" onClick={() => setShowPw(v => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px]"
                        style={{ color: 'var(--text-subtle)' }}>
                  {showPw ? t('common.hide') : t('common.show')}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1"
                     style={{ color: 'var(--text-muted)' }}>{t('setup.confirm_password')}</label>
              <div className="relative">
                <input type={showPw ? 'text' : 'password'} value={form.confirm}
                       onChange={e => setForm(p => ({ ...p, confirm: e.target.value }))}
                       required className={`${inputClass} pr-16`} />
              </div>
            </div>
            <button type="submit" disabled={loading}
                    className="w-full bg-steel-blue text-white font-semibold py-2.5 rounded-card hover:bg-steel-blue-700 transition-colors disabled:opacity-50">
              {loading ? t('setup.submitting') : t('setup.submit')}
            </button>
          </form>
        </div>

        <div className="flex justify-center mt-5">
          <div className="relative inline-flex items-center bg-gold border-2 border-gold rounded-card overflow-hidden">
            <span className="pl-3 text-deep-navy text-sm pointer-events-none">🌐</span>
            <select value={lang} onChange={e => setLang(e.target.value)}
                    style={{ background: 'transparent' }}
                    className="appearance-none text-[13px] font-semibold text-deep-navy pl-1.5 pr-7 py-1.5 cursor-pointer focus:outline-none">
              {SUPPORTED_LANGS.map(l => (
                <option key={l.code} value={l.code} style={{ background: '#1e3a5f', color: 'white' }}>{l.label}</option>
              ))}
            </select>
            <span className="absolute right-2 text-deep-navy text-[10px] pointer-events-none">▼</span>
          </div>
        </div>
        <p className="text-center text-[10px] mt-2" style={{ color: 'var(--text-subtle)' }}>
          {t('app.verse')}
        </p>
        <p className="text-center text-[10px] mt-1" style={{ color: 'var(--text-subtle)' }}>
          {MOIMIO_VERSION} · © Pistio
        </p>
      </div>
    </div>
  );
}
