import { useState, useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import { DateFormatProvider } from './hooks/useDateFormat';
import { ThemeProvider } from './hooks/useTheme';
import ProtectedRoute from './components/ProtectedRoute';
import AdminLayout from './components/AdminLayout';
import RouteLoading from './components/RouteLoading';

// v0.70: Public + auth routes lazy-loaded.
//
// Rationale: a participant landing on /register/:eventId or /confirm/:token
// previously downloaded the entire admin app (AllocationBoard, CheckInPanel,
// PeopleTable, etc.) just to view a registration form. Auth routes
// (login / forgot / reset) are visited briefly on first authentication
// then never again. Splitting them out shrinks the critical path for
// these single-shot visits without paying a navigation round-trip cost
// on the admin pages — admins navigate frequently between EventsPage,
// EventDetailPage, etc., and the PWA service worker (v0.59d) precaches
// the build graph anyway, so admin-route splitting has no perceptible
// benefit for installed-PWA users.
//
// SetupPage stays eager because it's rendered as a top-level conditional
// (not inside <Routes>) and only fires once per install — 7 KB raw isn't
// worth the wrapping.
const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const ConfirmPage = lazy(() => import('./pages/ConfirmPage'));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));

// Admin routes stay eager — see rationale above.
import EventsPage from './pages/EventsPage';
import EventDetailPage from './pages/EventDetailPage';
import OverviewPage from './pages/OverviewPage';
import CheckinOverlayPage from './pages/CheckinOverlayPage';
import SetupPage from './pages/SetupPage';
import BackupPage from './pages/BackupPage';
import UserManagementPage from './pages/UserManagementPage';
import WebhooksPage from './pages/WebhooksPage';
import WorkspacePage from './pages/WorkspacePage';
import { setup as setupApi } from './services/api';
import { I18nProvider } from './hooks/useI18n';
import { CapabilitiesProvider } from './hooks/useCapabilities';

function App() {
  const [needsSetup, setNeedsSetup] = useState(null); // null=loading, true, false
  const [setupError, setSetupError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      for (let attempt = 0; attempt < 8; attempt++) {
        try {
          const data = await setupApi.status();
          if (!cancelled) setNeedsSetup(data.needs_setup || (data.bootstrap_required && /^#bootstrap=[A-Za-z0-9_-]{32,128}$/.test(location.hash)));
          return;
        } catch {
          if (attempt < 7) await new Promise(r => setTimeout(r, 1500));
        }
      }
      if (!cancelled) setSetupError(true);
    };
    check();
    return () => { cancelled = true; };
  }, []);

  if (setupError) {
    return (
      <ThemeProvider>
        <div className="min-h-screen flex items-center justify-center"
             style={{ backgroundColor: 'var(--app-bg)' }}>
          <div className="text-center">
            <p className="text-sm mb-2" style={{ color: 'var(--text-subtle)' }}>
              Cannot reach the server.
            </p>
            <button onClick={() => { setSetupError(false); setNeedsSetup(null); }}
              className="text-steel-blue text-sm hover:underline">Retry</button>
          </div>
        </div>
      </ThemeProvider>
    );
  }

  if (needsSetup === null) {
    return (
      <ThemeProvider>
        <div className="min-h-screen flex items-center justify-center"
             style={{ backgroundColor: 'var(--app-bg)' }}>
          <p className="text-sm" style={{ color: 'var(--text-subtle)' }}>Loading...</p>
        </div>
      </ThemeProvider>
    );
  }

  if (needsSetup) {
    return (
      <ThemeProvider>
        <BrowserRouter>
          <I18nProvider>
            <SetupPage onComplete={() => setNeedsSetup(false)} />
          </I18nProvider>
        </BrowserRouter>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <I18nProvider>
          <CapabilitiesProvider>
          <DateFormatProvider>
            {/*
              v0.70: Suspense boundary for lazy-loaded public + auth
              routes. Eager admin routes inside the same <Routes> block
              do not trigger Suspense (their components are imported
              statically), so the fallback only fires on first navigation
              to /login, /register, /confirm, /forgot-password, or
              /reset-password.
            */}
            <Suspense fallback={<RouteLoading />}>
              <Routes>
                {/* Public routes (lazy) */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register/:eventId" element={<RegisterPage />} />
                <Route path="/confirm/:token" element={<ConfirmPage />} />
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password" element={<ResetPasswordPage />} />

                {/* Admin routes (eager) */}
                <Route path="/admin" element={<ProtectedRoute><AdminLayout /></ProtectedRoute>}>
                  <Route index element={<EventsPage />} />
                  <Route path="events/:eventId" element={<EventDetailPage />} />
                  <Route path="users" element={<UserManagementPage />} />
                  <Route path="backup" element={<BackupPage />} />
                  {/* v1.0.0g: outbound webhooks admin. The sidebar entry
                      is gated by useCapabilities().outbound_webhooks; the
                      route itself stays mounted because the backend
                      returns 404 when the capability is off, which is
                      a reasonable failure mode if someone hand-types the
                      URL while the flag is disabled. */}
                  <Route path="webhooks" element={<WebhooksPage />} />
                  <Route path="workspace" element={<WorkspacePage />} />
                </Route>

                {/* Full-screen overview (light + dark, §9.9) */}
                <Route path="/overview/:eventId/:categoryId" element={
                  <ProtectedRoute><OverviewPage /></ProtectedRoute>
                } />

                {/* Full-screen check-in mode (§5 — v50c-3c-2). Separate from
                    AdminLayout so there's no sidebar or event-header chrome. */}
                <Route path="/admin/events/:eventId/checkin" element={
                  <ProtectedRoute><CheckinOverlayPage /></ProtectedRoute>
                } />

                <Route path="*" element={<Navigate to="/admin" replace />} />
              </Routes>
            </Suspense>
          </DateFormatProvider>
          </CapabilitiesProvider>
          </I18nProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
