// Shared UI primitives for TooInvolved
// Theme tokens, Button, Crest, FormChip, BackButton, TopBar, etc.

// Theme is mutable via Tweaks. Keep simple — single accent + density.
const TI_DEFAULT_THEME = {
  bg:      'oklch(0.985 0.005 80)',   // warm off-white
  surface: '#ffffff',
  border:  'rgba(20, 18, 14, 0.08)',
  borderStrong: 'rgba(20, 18, 14, 0.14)',
  text:    'oklch(0.22 0.01 80)',     // near-black warm
  textMuted: 'oklch(0.52 0.01 80)',
  textFaint: 'oklch(0.68 0.01 80)',
  accent:  'oklch(0.62 0.16 145)',    // pitch green
  accentInk: '#ffffff',
  accentTint: 'oklch(0.96 0.04 145)', // very pale green for highlighted row
  win:    'oklch(0.62 0.16 145)',     // green
  draw:   'oklch(0.72 0.04 80)',      // warm gray
  loss:   'oklch(0.64 0.18 28)',      // coral
};

const TI_FONT = '"Inter", -apple-system, system-ui, sans-serif';
const TI_NUM_FONT = '"Inter", -apple-system, system-ui, sans-serif'; // tabular-nums applied via fontVariantNumeric

// ── Crest: a soft rounded square with team initials ──────────
function Crest({ name, color, size = 36 }) {
  const initials = (name || '?')
    .split(/\s+/)
    .filter(w => /[A-Za-z]/.test(w[0]))
    .slice(0, 2)
    .map(w => w[0].toUpperCase())
    .join('');
  return (
    <div style={{
      width: size, height: size, borderRadius: size * 0.28,
      background: color || '#888',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#fff', fontWeight: 700,
      fontSize: size * 0.4, letterSpacing: -0.3,
      flexShrink: 0,
      boxShadow: 'inset 0 -1px 0 rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.2)',
      fontFamily: TI_FONT,
    }}>{initials}</div>
  );
}

// ── Form chip: W/D/L pill ────────────────────────────────────
function FormChip({ result, size = 22, theme }) {
  const c = result === 'W' ? theme.win : result === 'L' ? theme.loss : theme.draw;
  const txt = result === 'D' ? theme.text : '#fff';
  return (
    <div style={{
      width: size, height: size, borderRadius: size * 0.28,
      background: c,
      color: txt,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 700, fontSize: size * 0.5, letterSpacing: 0,
      fontFamily: TI_FONT,
      flexShrink: 0,
    }}>{result}</div>
  );
}

// ── Primary button ───────────────────────────────────────────
function Button({ children, onClick, variant = 'primary', disabled, theme, leadingIcon, style }) {
  const styles = {
    primary: {
      background: disabled ? 'rgba(20,18,14,0.08)' : theme.accent,
      color: disabled ? theme.textFaint : theme.accentInk,
      border: 'none',
    },
    secondary: {
      background: '#fff',
      color: theme.text,
      border: `1px solid ${theme.borderStrong}`,
    },
    ghost: {
      background: 'transparent',
      color: theme.text,
      border: 'none',
    },
  };
  return (
    <button
      onClick={disabled ? undefined : onClick}
      style={{
        height: 52, borderRadius: 14, padding: '0 20px',
        fontFamily: TI_FONT, fontWeight: 600, fontSize: 16, letterSpacing: -0.2,
        cursor: disabled ? 'default' : 'pointer',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        width: '100%',
        transition: 'transform 80ms ease, opacity 120ms ease',
        ...styles[variant], ...(style || {}),
      }}
      onMouseDown={e => { if (!disabled) e.currentTarget.style.transform = 'scale(0.985)'; }}
      onMouseUp={e => { e.currentTarget.style.transform = 'scale(1)'; }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)'; }}
    >
      {leadingIcon}
      {children}
    </button>
  );
}

// ── Top bar with back + title (for non-modal screens) ────────
function TopBar({ title, onBack, right, theme, subtitle }) {
  return (
    <div style={{
      position: 'sticky', top: 0, zIndex: 5,
    }}>
      <div style={{ height: 54 }} />
      <div style={{
        paddingBottom: 12, paddingLeft: 16, paddingRight: 16, paddingTop: 4,
        display: 'flex', alignItems: 'center', gap: 8,
        background: theme.bg,
        borderBottom: `1px solid ${theme.border}`,
      }}>
      {onBack ? (
        <button onClick={onBack} style={{
          width: 36, height: 36, borderRadius: 10, border: 'none',
          background: 'transparent', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginLeft: -6,
        }}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M12.5 4L6.5 10l6 6" stroke={theme.text} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      ) : <div style={{ width: 36 }} />}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: TI_FONT, fontWeight: 700, fontSize: 17, color: theme.text,
          letterSpacing: -0.3, lineHeight: '20px',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{title}</div>
        {subtitle && (
          <div style={{
            fontFamily: TI_FONT, fontSize: 12, color: theme.textMuted,
            marginTop: 1, lineHeight: '14px',
          }}>{subtitle}</div>
        )}
      </div>
      {right || <div style={{ width: 36 }} />}
      </div>
    </div>
  );
}

// ── Status bar overlay (since we manage our own header) ─────
function StatusBarLight({ time = '9:41' }) {
  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, right: 0, zIndex: 30,
      height: 54, padding: '17px 28px 0', display: 'flex',
      alignItems: 'center', justifyContent: 'space-between',
      fontFamily: '-apple-system, "SF Pro Text", system-ui',
      pointerEvents: 'none',
    }}>
      <div style={{ fontWeight: 600, fontSize: 15, color: '#000' }}>{time}</div>
      <div style={{ width: 100 }} />
      <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
        <svg width="17" height="11" viewBox="0 0 17 11"><rect x="0" y="6" width="3" height="5" rx="0.6" fill="#000"/><rect x="4.5" y="4" width="3" height="7" rx="0.6" fill="#000"/><rect x="9" y="2" width="3" height="9" rx="0.6" fill="#000"/><rect x="13.5" y="0" width="3" height="11" rx="0.6" fill="#000"/></svg>
        <svg width="24" height="11" viewBox="0 0 24 11"><rect x="0.5" y="0.5" width="21" height="10" rx="2.5" stroke="#000" strokeOpacity="0.4" fill="none"/><rect x="2" y="2" width="18" height="7" rx="1.5" fill="#000"/><path d="M22.5 4v3c0.6-0.2 1-0.7 1-1.5s-0.4-1.3-1-1.5z" fill="#000" fillOpacity="0.4"/></svg>
      </div>
    </div>
  );
}

// ── Home indicator (already drawn by IOSDevice; keep here for reference) ─
// Provided by IOSDevice — don't duplicate.

// ── Segmented control ────────────────────────────────────────
function Segmented({ options, value, onChange, theme }) {
  return (
    <div style={{
      display: 'flex', background: 'rgba(20,18,14,0.05)',
      borderRadius: 12, padding: 3, gap: 2,
      fontFamily: TI_FONT,
    }}>
      {options.map(opt => {
        const active = opt.value === value;
        return (
          <button key={opt.value}
            onClick={() => onChange(opt.value)}
            style={{
              flex: 1, height: 34, borderRadius: 9, border: 'none',
              background: active ? '#fff' : 'transparent',
              color: active ? theme.text : theme.textMuted,
              fontWeight: active ? 600 : 500, fontSize: 13,
              cursor: 'pointer',
              boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06), 0 0 0 1px rgba(20,18,14,0.05)' : 'none',
              letterSpacing: -0.1,
              transition: 'all 120ms ease',
            }}>
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// ── Subtle divider ───────────────────────────────────────────
function Divider({ theme, inset = 0 }) {
  return <div style={{ height: 1, background: theme.border, marginLeft: inset }} />;
}

Object.assign(window, {
  TI_DEFAULT_THEME, TI_FONT, TI_NUM_FONT,
  Crest, FormChip, Button, TopBar, StatusBarLight, Segmented, Divider,
});
