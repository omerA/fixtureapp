// Auth + Onboarding screens for TooInvolved

function AuthScreen({ theme, onContinue }) {
  return (
    <div style={{
      minHeight: '100%', display: 'flex', flexDirection: 'column',
      background: theme.bg, padding: '88px 24px 40px',
      fontFamily: TI_FONT, color: theme.text,
    }}>
      {/* Brand mark */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 18 }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16,
          background: theme.accent,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 8px 24px rgba(20,18,14,0.08)',
        }}>
          <svg width="30" height="30" viewBox="0 0 30 30" fill="none">
            {/* abstract whistle / bracket mark */}
            <circle cx="15" cy="15" r="11" stroke="#fff" strokeWidth="2.4" fill="none"/>
            <circle cx="15" cy="15" r="3.4" fill="#fff"/>
          </svg>
        </div>
        <div>
          <div style={{ fontSize: 36, fontWeight: 800, letterSpacing: -1.2, lineHeight: '40px' }}>
            TooInvolved
          </div>
          <div style={{ fontSize: 17, color: theme.textMuted, marginTop: 8, lineHeight: '24px', maxWidth: 300 }}>
            Follow your kid's team. Standings, scores, and Saturday's kickoff — all in one place.
          </div>
        </div>
      </div>

      {/* placeholder visual hint */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '32px 0' }}>
        <div style={{
          width: '100%', maxWidth: 280, aspectRatio: '4/3',
          borderRadius: 20, background: theme.accentTint,
          border: `1px dashed ${theme.borderStrong}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: theme.textMuted, fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 11,
          letterSpacing: 0.2, padding: 16, textAlign: 'center',
        }}>
          hero illustration<br/>(parents + kid on sideline)
        </div>
      </div>

      {/* Auth buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button onClick={onContinue} style={{
          height: 52, borderRadius: 14, border: 'none', cursor: 'pointer',
          background: '#000', color: '#fff',
          fontFamily: TI_FONT, fontWeight: 600, fontSize: 16, letterSpacing: -0.2,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        }}>
          <svg width="17" height="20" viewBox="0 0 17 20" fill="#fff">
            <path d="M14.7 15.6c-.4.9-.9 1.7-1.5 2.5-.8 1-1.5 1.7-2 2-.8.5-1.7.8-2.6.8-.7 0-1.5-.2-2.4-.5-.9-.3-1.8-.5-2.5-.5-.8 0-1.6.2-2.5.5-.9.3-1.7.5-2.3.5-.9 0-1.8-.3-2.6-1l.1-.1c-.5-.5-1-1.2-1.5-2-.5-.9-.9-1.9-1.2-3-.4-1.2-.5-2.3-.5-3.5 0-1.3.3-2.4.8-3.4.5-.8 1.1-1.4 1.9-1.9.8-.5 1.7-.7 2.6-.7.7 0 1.6.2 2.6.6 1 .4 1.7.6 1.9.6.2 0 1-.2 2.2-.7 1.2-.4 2.2-.6 3-.5 2.2.2 3.8 1 4.9 2.5-2 1.2-2.9 2.8-2.9 4.9 0 1.6.6 3 1.7 4 .5.5 1.1.9 1.8 1.2-.2.4-.3.7-.5 1.1zM11.2 0c0 1-.4 1.9-1.1 2.7-.8.9-1.9 1.5-3 1.4 0-1 .4-1.9 1.1-2.7C9.1.5 10.2 0 11.2 0z" transform="translate(1.5,0)"/>
          </svg>
          Continue with Apple
        </button>
        <button onClick={onContinue} style={{
          height: 52, borderRadius: 14, cursor: 'pointer',
          background: '#fff', color: theme.text,
          border: `1px solid ${theme.borderStrong}`,
          fontFamily: TI_FONT, fontWeight: 600, fontSize: 16, letterSpacing: -0.2,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        }}>
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path d="M17.6 9.2c0-.6-.1-1.2-.2-1.8H9v3.4h4.8c-.2 1.1-.8 2-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.9 2.7-6.5z" fill="#4285F4"/>
            <path d="M9 18c2.4 0 4.5-.8 5.9-2.2l-2.9-2.2c-.8.5-1.8.9-3 .9-2.3 0-4.3-1.6-5-3.7H1v2.3C2.5 16 5.5 18 9 18z" fill="#34A853"/>
            <path d="M4 10.8c-.2-.5-.3-1.2-.3-1.8s.1-1.2.3-1.8V4.9H1C.4 6.2 0 7.6 0 9s.4 2.8 1 4.1L4 10.8z" fill="#FBBC05"/>
            <path d="M9 3.6c1.3 0 2.5.5 3.4 1.3l2.6-2.6C13.5.9 11.4 0 9 0 5.5 0 2.5 2 1 4.9L4 7.2c.7-2.1 2.7-3.6 5-3.6z" fill="#EA4335"/>
          </svg>
          Continue with Google
        </button>
        <div style={{ height: 8 }} />
        <div style={{
          fontSize: 12, color: theme.textFaint, textAlign: 'center', lineHeight: '16px',
          padding: '0 12px',
        }}>
          By continuing, you agree to our Terms and acknowledge our Privacy Policy.
        </div>
      </div>
    </div>
  );
}

// ─── Onboarding ──────────────────────────────────────────────
function OnboardingScreen({ theme, onDone, initiallySelected = [] }) {
  const [step, setStep] = React.useState(0); // 0: child age, 1: search teams, 2: confirm
  const [year, setYear] = React.useState('2016');
  const [month, setMonth] = React.useState('March');
  const [query, setQuery] = React.useState('');
  const [selected, setSelected] = React.useState(initiallySelected);

  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const years = Array.from({length: 12}, (_, i) => String(2026 - i - 4)); // 2018..2007 roughly

  const pool = window.TI_DATA.searchPool;
  const filtered = query.trim()
    ? pool.filter(t => t.name.toLowerCase().includes(query.toLowerCase()) ||
                       t.city.toLowerCase().includes(query.toLowerCase()))
    : pool;

  const toggle = (id) => {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
  };

  return (
    <div style={{
      minHeight: '100%', display: 'flex', flexDirection: 'column',
      background: theme.bg, fontFamily: TI_FONT, color: theme.text,
    }}>
      {/* Progress + header */}
      <div style={{ paddingTop: 60, paddingLeft: 24, paddingRight: 24, paddingBottom: 8 }}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 24 }}>
          {[0,1,2].map(i => (
            <div key={i} style={{
              flex: 1, height: 4, borderRadius: 2,
              background: i <= step ? theme.accent : 'rgba(20,18,14,0.08)',
              transition: 'background 200ms ease',
            }}/>
          ))}
        </div>
        <button onClick={() => step > 0 ? setStep(step - 1) : null}
          style={{
            background: 'transparent', border: 'none', cursor: step > 0 ? 'pointer' : 'default',
            padding: 0, marginBottom: 16, opacity: step > 0 ? 1 : 0,
            display: 'flex', alignItems: 'center', gap: 4, color: theme.textMuted,
            fontFamily: TI_FONT, fontSize: 14, fontWeight: 500,
          }}>
          <svg width="14" height="14" viewBox="0 0 14 14"><path d="M9 3L4 7l5 4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
          Back
        </button>
        <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: -0.8, lineHeight: '32px' }}>
          {step === 0 && "When was your kid born?"}
          {step === 1 && "Find your kid's team"}
          {step === 2 && "Almost there"}
        </div>
        <div style={{ fontSize: 15, color: theme.textMuted, marginTop: 8, lineHeight: '20px' }}>
          {step === 0 && "We'll use this to suggest the right age divisions and league levels."}
          {step === 1 && "Search by team name or city. Pick as many as you'd like."}
          {step === 2 && `${selected.length} ${selected.length === 1 ? 'team' : 'teams'} ready to follow. You can add or remove anytime.`}
        </div>
      </div>

      {/* Step content */}
      <div style={{ flex: 1, padding: '20px 24px 24px', overflowY: 'auto' }}>
        {step === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <PickerField label="Birth year" theme={theme}>
              <ScrollPicker options={years} value={year} onChange={setYear} theme={theme} />
            </PickerField>
            <PickerField label="Birth month" theme={theme}>
              <ScrollPicker options={months} value={month} onChange={setMonth} theme={theme} />
            </PickerField>
            <div style={{
              padding: 14, borderRadius: 12,
              background: theme.accentTint,
              fontSize: 13, color: theme.text,
              display: 'flex', gap: 10, alignItems: 'flex-start',
            }}>
              <svg width="16" height="16" viewBox="0 0 16 16" style={{ flexShrink: 0, marginTop: 2 }}>
                <circle cx="8" cy="8" r="7" stroke={theme.accent} strokeWidth="1.5" fill="none"/>
                <path d="M8 5v3.5M8 11v.5" stroke={theme.accent} strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
              <div>
                Most local leagues group kids by school-year birth ranges (Aug–Jul). Looks like your kid would be in <strong style={{ fontWeight: 700 }}>U10</strong>.
              </div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div>
            {/* Search field */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: '#fff', border: `1px solid ${theme.border}`,
              borderRadius: 14, padding: '0 14px', height: 48,
              marginBottom: 14,
            }}>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <circle cx="8" cy="8" r="6" stroke={theme.textMuted} strokeWidth="1.8"/>
                <path d="M13 13l3 3" stroke={theme.textMuted} strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="e.g. Eastbay Strikers"
                style={{
                  flex: 1, border: 'none', outline: 'none', background: 'transparent',
                  fontFamily: TI_FONT, fontSize: 16, color: theme.text,
                  letterSpacing: -0.2,
                }}
              />
              {query && (
                <button onClick={() => setQuery('')} style={{
                  background: 'rgba(20,18,14,0.08)', border: 'none', cursor: 'pointer',
                  width: 22, height: 22, borderRadius: 11,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  padding: 0,
                }}>
                  <svg width="10" height="10" viewBox="0 0 10 10"><path d="M2 2l6 6M8 2l-6 6" stroke={theme.textMuted} strokeWidth="1.8" strokeLinecap="round"/></svg>
                </button>
              )}
            </div>

            {selected.length > 0 && (
              <div style={{ fontSize: 12, color: theme.textMuted, marginBottom: 8, fontWeight: 600, letterSpacing: 0.2, textTransform: 'uppercase' }}>
                {selected.length} selected
              </div>
            )}

            <div style={{
              background: '#fff', borderRadius: 16, border: `1px solid ${theme.border}`,
              overflow: 'hidden',
            }}>
              {filtered.map((t, i) => {
                const on = selected.includes(t.id);
                return (
                  <div key={t.id}>
                    <button onClick={() => toggle(t.id)} style={{
                      width: '100%', background: on ? theme.accentTint : '#fff',
                      border: 'none', padding: '12px 14px',
                      display: 'flex', alignItems: 'center', gap: 12,
                      cursor: 'pointer', textAlign: 'left',
                      transition: 'background 120ms',
                    }}>
                      <Crest name={t.name} color="#888" size={36} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 15, fontWeight: 600, color: theme.text, letterSpacing: -0.2 }}>
                          {t.name}
                        </div>
                        <div style={{ fontSize: 12, color: theme.textMuted, marginTop: 2 }}>
                          {t.leagueLabel} · {t.city}
                        </div>
                      </div>
                      <div style={{
                        width: 24, height: 24, borderRadius: 8,
                        border: on ? 'none' : `1.5px solid ${theme.borderStrong}`,
                        background: on ? theme.accent : 'transparent',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0,
                      }}>
                        {on && <svg width="13" height="13" viewBox="0 0 13 13"><path d="M3 6.5L5.5 9 10 4" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                      </div>
                    </button>
                    {i < filtered.length - 1 && <Divider theme={theme} inset={62} />}
                  </div>
                );
              })}
              {filtered.length === 0 && (
                <div style={{ padding: 32, textAlign: 'center', color: theme.textMuted, fontSize: 14 }}>
                  No teams match "{query}".
                  <div style={{ marginTop: 6, fontSize: 12 }}>Try a different name or check spelling.</div>
                </div>
              )}
            </div>
          </div>
        )}

        {step === 2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {selected.map(id => {
              const t = pool.find(x => x.id === id);
              if (!t) return null;
              return (
                <div key={id} style={{
                  background: '#fff', borderRadius: 14,
                  border: `1px solid ${theme.border}`,
                  padding: 14, display: 'flex', alignItems: 'center', gap: 12,
                }}>
                  <Crest name={t.name} color={theme.accent} size={40} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: -0.2 }}>{t.name}</div>
                    <div style={{ fontSize: 12, color: theme.textMuted, marginTop: 2 }}>{t.leagueLabel}</div>
                  </div>
                  <svg width="18" height="18" viewBox="0 0 18 18">
                    <circle cx="9" cy="9" r="8" fill={theme.accent}/>
                    <path d="M5 9.5l2.5 2.5L13 6.5" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
              );
            })}
            {selected.length === 0 && (
              <div style={{
                padding: 24, borderRadius: 14, border: `1px dashed ${theme.borderStrong}`,
                textAlign: 'center', color: theme.textMuted, fontSize: 14,
                background: '#fff',
              }}>
                No teams yet. Go back and pick at least one.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: '12px 24px 24px',
        borderTop: `1px solid ${theme.border}`,
        background: theme.bg,
      }}>
        {step < 2 ? (
          <Button theme={theme} onClick={() => setStep(step + 1)}
            disabled={step === 1 && selected.length === 0}>
            Continue
          </Button>
        ) : (
          <Button theme={theme} onClick={() => onDone(selected)}
            disabled={selected.length === 0}>
            Start following
          </Button>
        )}
      </div>
    </div>
  );
}

function PickerField({ label, children, theme }) {
  return (
    <div>
      <div style={{
        fontSize: 12, fontWeight: 600, color: theme.textMuted,
        letterSpacing: 0.3, textTransform: 'uppercase', marginBottom: 6,
      }}>{label}</div>
      <div style={{
        background: '#fff', border: `1px solid ${theme.border}`,
        borderRadius: 14, overflow: 'hidden',
      }}>
        {children}
      </div>
    </div>
  );
}

function ScrollPicker({ options, value, onChange, theme }) {
  return (
    <div style={{
      display: 'flex', overflowX: 'auto', gap: 6, padding: 8,
      scrollbarWidth: 'none',
    }}>
      <style>{`.ti-pickr::-webkit-scrollbar { display: none }`}</style>
      <div className="ti-pickr" style={{ display: 'flex', gap: 6 }}>
        {options.map(opt => {
          const active = opt === value;
          return (
            <button key={opt} onClick={() => onChange(opt)} style={{
              padding: '8px 14px', borderRadius: 10, border: 'none',
              background: active ? theme.text : 'rgba(20,18,14,0.04)',
              color: active ? '#fff' : theme.text,
              fontFamily: TI_FONT, fontSize: 14, fontWeight: active ? 600 : 500,
              cursor: 'pointer', whiteSpace: 'nowrap',
              letterSpacing: -0.1,
            }}>{opt}</button>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { AuthScreen, OnboardingScreen });
