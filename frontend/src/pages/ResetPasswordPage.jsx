import { useState, useEffect } from 'react';
import { useI18n } from '../hooks/useI18n';
import { passwordReset, formatErrorMessage } from '../services/api';
import Wordmark from '../components/Wordmark';
import ThemeToggle from '../components/ThemeToggle';

// v0.59a-1: see LoginPage for rationale and pattern source.
const MOIMIO_VERSION = typeof __MOIMIO_VERSION__ !== 'undefined' ? __MOIMIO_VERSION__ : 'dev';

export default function ResetPasswordPage() {
  const [token] = useState(() => /^#reset=([A-Za-z0-9_-]{32,128})$/.exec(location.hash)?.[1]);
  useEffect(() => {
    // Never retain the bearer credential in history or accept old query links.
    if (location.hash || location.search) history.replaceState(null, '', location.pathname);
  }, []);
  const { t } = useI18n();

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);
  const [showPw, setShowPw] = useState(false);

  useEffect(() => {
    if (!token) setError(t('reset.error.no_token'));
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (password !== confirm) { setError(t('reset.error.mismatch')); return; }
    if (password.length < 8) { setError(t('reset.error.short')); return; }
    setLoading(true);
    try {
      await passwordReset.confirm(token, password);
      setDone(true);
      setTimeout(() => window.location.href = '/login', 3000);
    } catch (err) {
      setError(err.i18nKey === 'errors.auth.reset_expired' || err.i18nKey === 'errors.auth.reset_invalid' || (err.message && err.message.includes('expired')) ? t('reset.error.expired') : err);
    } finally { setLoading(false); }
  };

  const inputClass = "w-full rounded-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-steel-blue " +
                     "bg-white dark:bg-white/5 border border-card " +
                     "text-body disabled:opacity-50";

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
        </div>
        <div className="card-surface-solid p-6">
          {done ? (
            <div className="text-center">
              <div className="text-steel-blue text-4xl mb-3">✓</div>
              <h2 className="font-heading font-bold text-lg mb-2"
                  style={{ color: 'var(--text-primary)' }}>
                {t('reset.success.title')}
              </h2>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                {t('reset.success.message')}
              </p>
            </div>
          ) : (
            <>
              <h2 className="font-heading font-bold text-lg mb-1"
                  style={{ color: 'var(--text-primary)' }}>
                {t('reset.title')}
              </h2>
              <p className="text-xs mb-4" style={{ color: 'var(--text-subtle)' }}>
                {t('reset.subtitle')}
              </p>
              {error && (() => {
                const { primary, detail } = formatErrorMessage(error, t);
                // After v0.70d-3c-6: 'expired' UX hooks on the translated expired
                // string OR the i18n key. Inline string includes('expired') is the
                // legacy hook (when setError received t('reset.error.expired'));
                // i18nKey check covers structured error objects.
                const isExpired = (typeof error === 'string' && (error.includes('expired') || error.includes('Invalid'))) ||
                                  error?.i18nKey === 'errors.auth.reset_expired' ||
                                  error?.i18nKey === 'errors.auth.reset_invalid';
                return (
                  <div className="bg-alert-tint text-alert text-xs rounded-card p-2 mb-4">
                    <p className="font-semibold">{primary}</p>
                    {detail && <p className="text-xs opacity-70 mt-1">{detail}</p>}
                    {isExpired && (
                      <span> <button type="button" onClick={() => window.location.href = '/forgot-password'}
                        className="underline font-semibold bg-transparent border-none cursor-pointer text-alert">
                        {t('reset.request_new')}
                      </button></span>
                    )}
                  </div>
                );
              })()}
              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold mb-1"
                         style={{ color: 'var(--text-muted)' }}>{t('reset.password')}</label>
                  <div className="relative">
                    <input type={showPw ? 'text' : 'password'} value={password}
                           onChange={e => setPassword(e.target.value)}
                           required autoFocus disabled={!token}
                           className={`${inputClass} pr-16`} />
                    <button type="button" onClick={() => setShowPw(v => !v)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px]"
                            style={{ color: 'var(--text-subtle)' }}>
                      {showPw ? t('common.hide') : t('common.show')}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold mb-1"
                         style={{ color: 'var(--text-muted)' }}>{t('reset.confirm')}</label>
                  <div className="relative">
                    <input type={showPw ? 'text' : 'password'} value={confirm}
                           onChange={e => setConfirm(e.target.value)}
                           required disabled={!token}
                           className={`${inputClass} pr-16`} />
                  </div>
                </div>
                <button type="submit" disabled={loading || !token}
                        className="w-full bg-steel-blue text-white font-semibold py-2.5 rounded-card hover:bg-steel-blue-700 transition-colors disabled:opacity-50">
                  {loading ? t('reset.submitting') : t('reset.submit')}
                </button>
              </form>
              <div className="mt-4 text-center">
                <button type="button" onClick={() => window.location.href = '/login'}
                        className="text-xs bg-transparent border-none cursor-pointer hover:text-deep-navy dark:hover:text-off-white"
                        style={{ color: 'var(--text-subtle)' }}>
                  {t('reset.back')}
                </button>
              </div>
            </>
          )}
        </div>
        <p className="text-center text-[10px] mt-6" style={{ color: 'var(--text-subtle)' }}>
          {t('app.verse')}
        </p>
        <p className="text-center text-[10px] mt-1" style={{ color: 'var(--text-subtle)' }}>
          {MOIMIO_VERSION} · © Pistio
        </p>
      </div>
    </div>
  );
}
