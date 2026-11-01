import { StrictMode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, waitFor } from '@testing-library/react';
import ResetPasswordPage from './ResetPasswordPage';
import { I18nProvider } from '../hooks/useI18n';
import { passwordReset } from '../services/api';

vi.mock('../services/api', () => ({passwordReset:{confirm:vi.fn()},formatErrorMessage:()=>({primary:'Refused'})}));
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); history.replaceState(null,'','/reset-password'); });

describe('private reset fragment', () => {
  it('survives StrictMode and removes the credential before submission', async () => {
    const token='f'.repeat(64);
    history.replaceState(null,'','/reset-password#reset='+token);
    passwordReset.confirm.mockResolvedValue({});
    const {container}=render(<StrictMode><I18nProvider><ResetPasswordPage/></I18nProvider></StrictMode>);
    expect(location.hash).toBe('');expect(location.search).toBe('');
    const fields=container.querySelectorAll('input[type=password]');
    fireEvent.change(fields[0],{target:{value:'Fictional-password-only'}});
    fireEvent.change(fields[1],{target:{value:'Fictional-password-only'}});
    fireEvent.submit(container.querySelector('form'));
    await waitFor(()=>expect(passwordReset.confirm).toHaveBeenCalledWith(token,'Fictional-password-only'));
    expect(passwordReset.confirm).toHaveBeenCalledTimes(1);
  });
  it.each(['?token='+ 'f'.repeat(64),'#reset=short',''])('refuses absent, short or historical query authority: %s', value=>{
    history.replaceState(null,'','/reset-password'+value);
    const {container}=render(<I18nProvider><ResetPasswordPage/></I18nProvider>);
    expect(container.querySelector('button[type=submit]')).toBeDisabled();
    expect(location.search).toBe('');expect(location.hash).toBe('');
    expect(passwordReset.confirm).not.toHaveBeenCalled();
  });
});
