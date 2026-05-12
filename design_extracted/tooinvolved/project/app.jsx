// Main TooInvolved app — routing + tweaks + mount

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#2EA76A",
  "density": "comfy",
  "standingsLayout": "twoline",
  "startScreen": "auth"
}/*EDITMODE-END*/;

// Curated accent palette (hex -> oklch tint applied via JS)
const ACCENT_PRESETS = {
  '#2EA76A': { accent: 'oklch(0.62 0.16 145)', tint: 'oklch(0.96 0.04 145)', win: 'oklch(0.62 0.16 145)' },  // green (default)
  '#2B6FD9': { accent: 'oklch(0.55 0.18 260)', tint: 'oklch(0.96 0.03 260)', win: 'oklch(0.62 0.16 145)' },  // blue
  '#E25A2F': { accent: 'oklch(0.64 0.18 40)',  tint: 'oklch(0.96 0.04 40)',  win: 'oklch(0.62 0.16 145)' },  // coral
  '#6B4FE8': { accent: 'oklch(0.55 0.20 290)', tint: 'oklch(0.96 0.04 290)', win: 'oklch(0.62 0.16 145)' },  // purple
};

function buildTheme(tweaks) {
  const preset = ACCENT_PRESETS[tweaks.accent] || ACCENT_PRESETS['#2EA76A'];
  return {
    ...TI_DEFAULT_THEME,
    accent: preset.accent,
    accentTint: preset.tint,
    win: preset.win,
  };
}

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const theme = React.useMemo(() => buildTheme(tweaks), [tweaks]);

  // ── Navigation state ──
  // screen: 'auth' | 'onboarding' | 'teams' | 'detail' | 'add'
  const [screen, setScreen] = React.useState(tweaks.startScreen || 'auth');
  const [subscribedIds, setSubscribedIds] = React.useState(['tenafly']);
  const [activeTeamId, setActiveTeamId] = React.useState(null);

  // Keep screen in sync if user changes startScreen tweak
  React.useEffect(() => {
    if (tweaks.startScreen && tweaks.startScreen !== screen) {
      // only jump if it's a top-level screen, not detail
      if (['auth','onboarding','teams'].includes(tweaks.startScreen)) {
        setScreen(tweaks.startScreen);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tweaks.startScreen]);

  const goAuth = () => setScreen('auth');
  const goOnboarding = () => setScreen('onboarding');
  const goTeams = () => setScreen('teams');
  const openTeam = (id) => { setActiveTeamId(id); setScreen('detail'); };
  const addTeamFlow = () => setScreen('add');

  return (
    <div style={{
      minHeight: '100vh', background: '#ECECEF',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '32px 16px',
      fontFamily: TI_FONT,
    }}>
      <IOSDevice width={402} height={874}>
        <div style={{ height: '100%', overflowY: 'auto' }}>
          {screen === 'auth' && (
            <AuthScreen theme={theme} onContinue={() => setScreen(subscribedIds.length ? 'teams' : 'onboarding')} />
          )}
          {screen === 'onboarding' && (
            <OnboardingScreen theme={theme}
              initiallySelected={subscribedIds}
              onDone={(ids) => { setSubscribedIds(ids); setScreen('teams'); }}
            />
          )}
          {screen === 'teams' && (
            <MyTeamsScreen theme={theme}
              subscribedIds={subscribedIds}
              density={tweaks.density}
              onOpenTeam={openTeam}
              onAddTeam={addTeamFlow}
            />
          )}
          {screen === 'add' && (
            <OnboardingScreen theme={theme}
              initiallySelected={subscribedIds}
              onDone={(ids) => { setSubscribedIds(ids); setScreen('teams'); }}
            />
          )}
          {screen === 'detail' && activeTeamId && (
            <TeamDetailScreen theme={theme}
              teamId={activeTeamId}
              density={tweaks.density}
              standingsLayout={tweaks.standingsLayout}
              onBack={() => setScreen('teams')}
            />
          )}
        </div>
      </IOSDevice>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Theme">
          <TweakColor
            label="Accent"
            value={tweaks.accent}
            options={['#2EA76A', '#2B6FD9', '#E25A2F', '#6B4FE8']}
            onChange={v => setTweak('accent', v)}
          />
        </TweakSection>
        <TweakSection label="Layout">
          <TweakSelect
            label="Standings layout"
            value={tweaks.standingsLayout}
            options={[
              { value: 'twoline', label: 'A · Two-line (name + stats below)' },
              { value: 'compact', label: 'B · Compact (W/D/L/PTS only)'      },
              { value: 'scroll',  label: 'C · Scroll (sticky name + swipe)'  },
              { value: 'cards',   label: 'D · Cards (one per team)'          },
            ]}
            onChange={v => setTweak('standingsLayout', v)}
          />
          <TweakRadio
            label="Density"
            value={tweaks.density}
            options={[
              { value: 'comfy',   label: 'Comfy'   },
              { value: 'compact', label: 'Compact' },
            ]}
            onChange={v => setTweak('density', v)}
          />
        </TweakSection>
        <TweakSection label="Jump to screen">
          <TweakSelect
            label="Screen"
            value={screen}
            options={[
              { value: 'auth',       label: '1. Sign up'        },
              { value: 'onboarding', label: '2. Onboarding'     },
              { value: 'teams',      label: '3. My teams'       },
              { value: 'detail',     label: '4. Team detail'    },
            ]}
            onChange={v => {
              if (v === 'detail') {
                setActiveTeamId(activeTeamId || subscribedIds[0] || 'tenafly');
              }
              setScreen(v);
            }}
          />
          <TweakSelect
            label="Active team (for detail)"
            value={activeTeamId || 'tenafly'}
            options={[
              { value: 'tenafly', label: 'Tenafly SC (B13B)' },
            ]}
            onChange={v => { setActiveTeamId(v); if (screen === 'detail') setScreen('detail'); }}
          />
        </TweakSection>
        <TweakSection label="Demo">
          <TweakButton onClick={() => { setSubscribedIds([]); setScreen('auth'); }}>
            Reset to brand-new user
          </TweakButton>
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
