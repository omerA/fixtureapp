// My Teams (list) + Team Detail screens for TooInvolved

function MyTeamsScreen({ theme, subscribedIds, onOpenTeam, onAddTeam, density }) {
  const { teams, leagues } = window.TI_DATA;
  const subs = subscribedIds.map(id => teams[id]).filter(Boolean);

  return (
    <div style={{
      minHeight: '100%', background: theme.bg, fontFamily: TI_FONT, color: theme.text,
      display: 'flex', flexDirection: 'column',
    }}>
      <div style={{
        paddingTop: 58, paddingLeft: 20, paddingRight: 20, paddingBottom: 8,
        display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 10,
      }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: theme.textMuted, letterSpacing: 0.4, textTransform: 'uppercase' }}>
            Saturday morning
          </div>
          <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: -1, lineHeight: '34px', marginTop: 2 }}>
            My teams
          </div>
        </div>
        <button onClick={onAddTeam} style={{
          width: 42, height: 42, borderRadius: 12,
          background: '#fff', border: `1px solid ${theme.borderStrong}`,
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="18" height="18" viewBox="0 0 18 18"><path d="M9 3v12M3 9h12" stroke={theme.text} strokeWidth="2" strokeLinecap="round"/></svg>
        </button>
      </div>

      <div style={{ flex: 1, padding: '12px 16px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Next match highlight card */}
        {subs.length > 0 && (() => {
          const t = subs[0];
          const next = t.schedule.find(g => g.status === 'upcoming');
          if (!next) return null;
          const isHome = next.home === t.name;
          const opp = isHome ? next.away : next.home;
          return (
            <div style={{
              background: theme.accent, color: '#fff',
              borderRadius: 18, padding: 16,
              boxShadow: '0 4px 14px rgba(20,18,14,0.06)',
              position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', right: -40, top: -40,
                width: 160, height: 160, borderRadius: 80,
                background: 'rgba(255,255,255,0.08)',
              }}/>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, position: 'relative' }}>
                <div style={{
                  fontSize: 11, fontWeight: 700, letterSpacing: 0.6, textTransform: 'uppercase',
                  background: 'rgba(255,255,255,0.18)', padding: '3px 8px', borderRadius: 6,
                }}>Next up</div>
                <div style={{ fontSize: 12, opacity: 0.85, fontWeight: 500 }}>{formatDate(next.date)} · {next.time}</div>
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.6, lineHeight: '26px', position: 'relative' }}>
                {isHome ? 'vs' : '@'} {opp}
              </div>
              <div style={{ fontSize: 13, opacity: 0.85, marginTop: 4, position: 'relative' }}>
                {next.venue}
              </div>
              <div style={{
                marginTop: 12, display: 'flex', gap: 6, alignItems: 'center', position: 'relative',
                fontSize: 12, opacity: 0.9,
              }}>
                <Crest name={t.name} color="rgba(255,255,255,0.25)" size={20} />
                <span style={{ fontWeight: 600 }}>{t.name}</span>
              </div>
            </div>
          );
        })()}

        <div style={{ fontSize: 12, fontWeight: 600, color: theme.textMuted, letterSpacing: 0.4, textTransform: 'uppercase', marginTop: 4, paddingLeft: 4 }}>
          Following · {subs.length}
        </div>

        {subs.map(t => {
          const league = leagues[t.leagueId];
          const row = league.standings.find(s => s.id === t.id);
          const rank = league.standings.findIndex(s => s.id === t.id) + 1;
          return (
            <button key={t.id} onClick={() => onOpenTeam(t.id)} style={{
              background: '#fff', border: `1px solid ${theme.border}`,
              borderRadius: 18, padding: density === 'compact' ? 12 : 16,
              cursor: 'pointer', textAlign: 'left',
              display: 'flex', flexDirection: 'column', gap: 12,
              fontFamily: TI_FONT,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Crest name={t.name} color={t.crest} size={44} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: -0.3, color: theme.text }}>
                    {t.name}
                  </div>
                  <div style={{ fontSize: 12, color: theme.textMuted, marginTop: 2 }}>
                    {league.name} · #{rank} of {league.standings.length}
                  </div>
                </div>
                <svg width="16" height="16" viewBox="0 0 16 16"><path d="M6 3l5 5-5 5" stroke={theme.textFaint} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </div>

              {/* Stat strip */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
                background: 'rgba(20,18,14,0.025)', borderRadius: 12,
                padding: '10px 8px',
              }}>
                <StatBlock label="Rank" value={`#${rank}`} theme={theme} accent />
                <StatBlock label="W" value={row.w} theme={theme} />
                <StatBlock label="D" value={row.d} theme={theme} />
                <StatBlock label="L" value={row.l} theme={theme} />
                <StatBlock label="Pts" value={row.pts} theme={theme} bold />
              </div>

              {/* Form */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: theme.textMuted, letterSpacing: 0.4, textTransform: 'uppercase' }}>Form</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  {t.form.map((r, i) => <FormChip key={i} result={r} size={20} theme={theme} />)}
                </div>
                <div style={{ flex: 1 }}/>
                <span style={{ fontSize: 11, color: theme.textFaint }}>last 5</span>
              </div>
            </button>
          );
        })}

        {subs.length === 0 && (
          <div style={{
            padding: 28, borderRadius: 16, border: `1px dashed ${theme.borderStrong}`,
            textAlign: 'center', color: theme.textMuted, fontSize: 14, background: '#fff',
          }}>
            You're not following any teams yet.
            <div style={{ marginTop: 12 }}>
              <Button theme={theme} onClick={onAddTeam} style={{ height: 40, fontSize: 14, width: 'auto', padding: '0 18px' }}>
                Add a team
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatBlock({ label, value, theme, accent, bold }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
      <div style={{
        fontSize: bold ? 17 : 15, fontWeight: bold || accent ? 700 : 600,
        color: accent ? theme.accent : theme.text,
        fontVariantNumeric: 'tabular-nums', letterSpacing: -0.2,
        fontFamily: TI_FONT,
      }}>{value}</div>
      <div style={{
        fontSize: 10, fontWeight: 600, color: theme.textMuted,
        letterSpacing: 0.4, textTransform: 'uppercase',
      }}>{label}</div>
    </div>
  );
}

function formatDate(iso) {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

// ─── Team detail ─────────────────────────────────────────────
function TeamDetailScreen({ theme, teamId, onBack, density, standingsLayout }) {
  const [tab, setTab] = React.useState('standings');
  const { teams, leagues } = window.TI_DATA;
  const team = teams[teamId];
  const league = leagues[team.leagueId];
  const myRow = league.standings.find(s => s.id === team.id);
  const myRank = league.standings.findIndex(s => s.id === team.id) + 1;

  return (
    <div style={{
      minHeight: '100%', background: theme.bg, fontFamily: TI_FONT, color: theme.text,
      display: 'flex', flexDirection: 'column',
    }}>
      <TopBar title={team.name} subtitle={league.name} onBack={onBack} theme={theme}
        right={
          <button style={{
            width: 36, height: 36, borderRadius: 10, border: 'none',
            background: 'transparent', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: -6,
          }}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 3v12M10 15l-4-4M10 15l4-4M4 17h12" stroke={theme.text} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        }
      />

      {/* Hero summary */}
      <div style={{ padding: '18px 20px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <Crest name={team.name} color={team.crest} size={56} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.6, lineHeight: '26px' }}>{team.name}</div>
            <div style={{ fontSize: 12, color: theme.textMuted, marginTop: 4 }}>
              {team.childName} · #{team.jerseyNumber} · {league.season}
            </div>
          </div>
        </div>

        {/* Rank + Form summary */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr',
          gap: 10, marginTop: 14,
        }}>
          <div style={{
            background: '#fff', border: `1px solid ${theme.border}`,
            borderRadius: 14, padding: 12,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: theme.textMuted, letterSpacing: 0.5, textTransform: 'uppercase' }}>
              League position
            </div>
            <div style={{
              fontSize: 28, fontWeight: 800, letterSpacing: -0.8,
              color: theme.accent, marginTop: 2, lineHeight: '32px',
              fontVariantNumeric: 'tabular-nums',
            }}>
              #{myRank} <span style={{ fontSize: 13, color: theme.textMuted, fontWeight: 500 }}>of {league.standings.length}</span>
            </div>
            <div style={{ fontSize: 12, color: theme.text, marginTop: 4 }}>
              <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{myRow.pts}</span> pts ·{' '}
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>{myRow.gf}–{myRow.ga}</span> GD{' '}
              <span style={{
                color: (myRow.gf - myRow.ga) >= 0 ? theme.accent : theme.loss,
                fontWeight: 700, fontVariantNumeric: 'tabular-nums',
              }}>{(myRow.gf - myRow.ga) >= 0 ? '+' : ''}{myRow.gf - myRow.ga}</span>
            </div>
          </div>

          <div style={{
            background: '#fff', border: `1px solid ${theme.border}`,
            borderRadius: 14, padding: 12,
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: theme.textMuted, letterSpacing: 0.5, textTransform: 'uppercase' }}>
              Last 5
            </div>
            <div style={{ display: 'flex', gap: 5, marginTop: 8 }}>
              {team.form.map((r, i) => <FormChip key={i} result={r} size={26} theme={theme} />)}
            </div>
            <div style={{ fontSize: 12, color: theme.text, marginTop: 7, fontVariantNumeric: 'tabular-nums' }}>
              {team.form.filter(r => r === 'W').length}W · {team.form.filter(r => r === 'D').length}D · {team.form.filter(r => r === 'L').length}L
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ padding: '14px 16px 0', position: 'sticky', top: 80, background: theme.bg, zIndex: 5 }}>
        <Segmented theme={theme} value={tab} onChange={setTab}
          options={[
            { value: 'standings', label: 'Standings' },
            { value: 'schedule',  label: 'Schedule'  },
            { value: 'results',   label: 'Results'   },
          ]}
        />
      </div>

      <div style={{ flex: 1, padding: '14px 16px 40px' }}>
        {tab === 'standings' && <StandingsTable league={league} myTeamId={team.id} theme={theme} density={density} layout={standingsLayout} />}
        {tab === 'schedule'  && <ScheduleList team={team} theme={theme} kind="upcoming" />}
        {tab === 'results'   && <ScheduleList team={team} theme={theme} kind="final" />}
      </div>
    </div>
  );
}

// ── Standings: 4 layout variants ──────────────────────────────
// 'twoline'   — name on its own line, stats inline below (recommended)
// 'compact'   — single row but drop GF/GA/GD (W/D/L/PTS only)
// 'scroll'    — sticky team column + horizontal-scroll full stats
// 'cards'     — each team is a generous card with big PTS

function StandingsTable({ league, myTeamId, theme, density, layout = 'twoline' }) {
  const p = { league, myTeamId, theme, density };
  if (layout === 'compact') return <StandingsCompact {...p} />;
  if (layout === 'scroll')  return <StandingsScroll  {...p} />;
  if (layout === 'cards')   return <StandingsCards   {...p} />;
  return <StandingsTwoLine {...p} />;
}

// ─── A: Two-line ───
function StandingsTwoLine({ league, myTeamId, theme, density }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 16,
      border: `1px solid ${theme.border}`, overflow: 'hidden',
    }}>
      {league.standings.map((row, i) => {
        const isMe = row.id === myTeamId;
        const gd = row.gf - row.ga;
        const rank = i + 1;
        return (
          <div key={row.id} style={{
            position: 'relative',
            padding: density === 'compact' ? '8px 12px 9px' : '11px 14px 12px',
            background: isMe ? theme.accentTint : 'transparent',
            borderBottom: i < league.standings.length - 1 ? `1px solid ${theme.border}` : 'none',
          }}>
            {isMe && <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: theme.accent }} />}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 18, textAlign: 'center', fontSize: 13,
                fontWeight: isMe ? 800 : 600,
                color: isMe ? theme.accent : theme.textMuted,
                fontVariantNumeric: 'tabular-nums',
              }}>{rank}</div>
              <Crest name={row.name} color={row.crest} size={28} />
              <div style={{
                flex: 1, minWidth: 0,
                fontSize: 15, fontWeight: isMe ? 700 : 600,
                color: theme.text, letterSpacing: -0.2,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{row.name}</div>
              <div style={{
                fontSize: 18, fontWeight: 800, letterSpacing: -0.4,
                color: isMe ? theme.accent : theme.text,
                fontVariantNumeric: 'tabular-nums', textAlign: 'right',
              }}>{row.pts}</div>
              <div style={{
                fontSize: 10, fontWeight: 700, color: theme.textMuted,
                letterSpacing: 0.4, textTransform: 'uppercase',
                width: 20, textAlign: 'left',
              }}>pts</div>
            </div>
            <div style={{
              marginLeft: 40, marginTop: 4,
              display: 'flex', alignItems: 'center', gap: 12,
              fontSize: 12, color: theme.textMuted,
              fontVariantNumeric: 'tabular-nums', letterSpacing: -0.1,
            }}>
              <span><strong style={{ color: theme.text, fontWeight: 600 }}>{row.mp}</strong> GP</span>
              <span style={{ display: 'inline-flex', gap: 5 }}>
                <span style={{ color: theme.win, fontWeight: 700 }}>{row.w}W</span>
                <span style={{ opacity: 0.4 }}>·</span>
                <span style={{ color: theme.text, fontWeight: 700 }}>{row.d}D</span>
                <span style={{ opacity: 0.4 }}>·</span>
                <span style={{ color: theme.loss, fontWeight: 700 }}>{row.l}L</span>
              </span>
              <span><strong style={{ color: theme.text, fontWeight: 600 }}>{row.gf}:{row.ga}</strong></span>
              <span style={{
                color: gd > 0 ? theme.accent : gd < 0 ? theme.loss : theme.textMuted,
                fontWeight: 700,
              }}>{gd > 0 ? '+' : ''}{gd}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── B: Compact (W/D/L/PTS only) ───
function StandingsCompact({ league, myTeamId, theme, density }) {
  const rowH = density === 'compact' ? 38 : 44;
  const cols = [
    { k: 'mp',  l: 'MP'  },
    { k: 'w',   l: 'W'   },
    { k: 'd',   l: 'D'   },
    { k: 'l',   l: 'L'   },
    { k: 'pts', l: 'PTS', b: true },
  ];
  const grid = `22px minmax(0, 1fr) repeat(${cols.length}, 30px)`;
  return (
    <div style={{ background: '#fff', borderRadius: 16, border: `1px solid ${theme.border}`, overflow: 'hidden' }}>
      <div style={{
        display: 'grid', gridTemplateColumns: grid, gap: 6,
        alignItems: 'center', padding: '10px 12px 8px',
        fontSize: 10, fontWeight: 700, color: theme.textMuted,
        letterSpacing: 0.4, textTransform: 'uppercase',
        borderBottom: `1px solid ${theme.border}`, background: 'rgba(20,18,14,0.02)',
      }}>
        <div>#</div><div>Team</div>
        {cols.map(c => <div key={c.k} style={{ textAlign: 'right' }}>{c.l}</div>)}
      </div>
      {league.standings.map((row, i) => {
        const isMe = row.id === myTeamId;
        return (
          <div key={row.id} style={{
            display: 'grid', gridTemplateColumns: grid, gap: 6,
            alignItems: 'center', padding: '0 12px', height: rowH,
            background: isMe ? theme.accentTint : 'transparent',
            borderBottom: i < league.standings.length - 1 ? `1px solid ${theme.border}` : 'none',
            position: 'relative', fontSize: 13, color: theme.text,
            fontVariantNumeric: 'tabular-nums',
          }}>
            {isMe && <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: theme.accent }} />}
            <div style={{
              fontWeight: isMe ? 800 : 600,
              color: isMe ? theme.accent : theme.textMuted, fontSize: 12,
            }}>{i + 1}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
              <Crest name={row.name} color={row.crest} size={22} />
              <div style={{
                fontWeight: isMe ? 700 : 500, fontSize: 13,
                color: theme.text, letterSpacing: -0.1,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>{row.name}</div>
            </div>
            {cols.map(c => (
              <div key={c.k} style={{
                textAlign: 'right',
                fontWeight: c.b || isMe ? 700 : 500,
                fontSize: c.b ? 14 : 13, color: theme.text,
              }}>{row[c.k]}</div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

// ─── C: Horizontal scroll with sticky team column ───
function StandingsScroll({ league, myTeamId, theme, density }) {
  const rowH = density === 'compact' ? 42 : 48;
  const cols = [
    { k: 'mp',  l: 'MP'  },
    { k: 'w',   l: 'W'   },
    { k: 'd',   l: 'D'   },
    { k: 'l',   l: 'L'   },
    { k: 'gf',  l: 'GF'  },
    { k: 'ga',  l: 'GA'  },
    { k: 'gd',  l: 'GD'  },
    { k: 'pts', l: 'PTS', b: true },
  ];
  const stickyW = 174;
  return (
    <div style={{
      background: '#fff', borderRadius: 16,
      border: `1px solid ${theme.border}`, overflow: 'hidden',
    }}>
      <div style={{ position: 'relative', overflowX: 'auto' }}>
        <style>{`.ti-stscroll::-webkit-scrollbar { height: 0; }`}</style>
        <div className="ti-stscroll" style={{ minWidth: '100%', display: 'inline-block' }}>
          {/* Header */}
          <div style={{
            display: 'flex', alignItems: 'center', height: 32,
            background: 'rgba(20,18,14,0.02)',
            borderBottom: `1px solid ${theme.border}`,
          }}>
            <div style={{
              position: 'sticky', left: 0, zIndex: 2,
              width: stickyW, padding: '0 10px 0 12px',
              background: 'rgba(244,243,239,0.98)',
              fontSize: 10, fontWeight: 700, color: theme.textMuted,
              letterSpacing: 0.4, textTransform: 'uppercase',
              display: 'flex', alignItems: 'center',
              boxShadow: '4px 0 8px -6px rgba(20,18,14,0.18)',
              height: 32,
            }}>#&nbsp;&nbsp;Team</div>
            {cols.map(c => (
              <div key={c.k} style={{
                width: 38, textAlign: 'center',
                fontSize: 10, fontWeight: 700, color: theme.textMuted,
                letterSpacing: 0.4,
              }}>{c.l}</div>
            ))}
          </div>
          {league.standings.map((row, i) => {
            const isMe = row.id === myTeamId;
            const gd = row.gf - row.ga;
            const meBg = isMe ? theme.accentTint : '#fff';
            return (
              <div key={row.id} style={{
                display: 'flex', alignItems: 'center', height: rowH,
                background: meBg,
                borderBottom: i < league.standings.length - 1 ? `1px solid ${theme.border}` : 'none',
              }}>
                <div style={{
                  position: 'sticky', left: 0, zIndex: 1,
                  width: stickyW, height: '100%',
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '0 10px 0 12px', background: meBg,
                  boxShadow: '4px 0 8px -6px rgba(20,18,14,0.18)',
                  position: 'sticky',
                }}>
                  {isMe && <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: theme.accent }} />}
                  <div style={{
                    width: 14, textAlign: 'center', fontSize: 12,
                    fontWeight: isMe ? 800 : 600,
                    color: isMe ? theme.accent : theme.textMuted,
                    fontVariantNumeric: 'tabular-nums',
                  }}>{i + 1}</div>
                  <Crest name={row.name} color={row.crest} size={24} />
                  <div style={{
                    fontSize: 13, fontWeight: isMe ? 700 : 600,
                    color: theme.text, letterSpacing: -0.1,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    minWidth: 0,
                  }}>{row.name}</div>
                </div>
                {cols.map(c => {
                  const v = c.k === 'gd' ? (gd > 0 ? `+${gd}` : `${gd}`) : row[c.k];
                  return (
                    <div key={c.k} style={{
                      width: 38, textAlign: 'center',
                      fontSize: c.b ? 14 : 13,
                      fontWeight: c.b || isMe ? 700 : 500,
                      color: c.k === 'gd' && gd < 0 ? theme.loss
                           : c.k === 'gd' && gd > 0 ? theme.accent
                           : theme.text,
                      fontVariantNumeric: 'tabular-nums',
                    }}>{v}</div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
      <div style={{
        fontSize: 11, color: theme.textFaint,
        padding: '7px 12px', borderTop: `1px solid ${theme.border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4,
      }}>
        Swipe for all stats
        <svg width="11" height="11" viewBox="0 0 12 12">
          <path d="M3 6h6m0 0L6 3m3 3L6 9" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
    </div>
  );
}

// ─── D: Cards ───
function StandingsCards({ league, myTeamId, theme, density }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {league.standings.map((row, i) => {
        const isMe = row.id === myTeamId;
        const gd = row.gf - row.ga;
        return (
          <div key={row.id} style={{
            background: isMe ? theme.accentTint : '#fff',
            border: `1px solid ${isMe ? theme.accent : theme.border}`,
            borderRadius: 14, padding: density === 'compact' ? 10 : 12,
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{
              width: 26, textAlign: 'center',
              fontSize: 18, fontWeight: 800,
              color: isMe ? theme.accent : (i === 0 ? theme.text : theme.textMuted),
              fontVariantNumeric: 'tabular-nums', letterSpacing: -0.4,
            }}>{i + 1}</div>
            <Crest name={row.name} color={row.crest} size={38} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 15, fontWeight: isMe ? 700 : 600,
                color: theme.text, letterSpacing: -0.2,
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>{row.name}</div>
              <div style={{
                display: 'flex', gap: 6, marginTop: 4, alignItems: 'center',
                fontSize: 11, fontVariantNumeric: 'tabular-nums',
              }}>
                <StChip kind="win"  theme={theme}>{row.w}W</StChip>
                <StChip kind="draw" theme={theme}>{row.d}D</StChip>
                <StChip kind="loss" theme={theme}>{row.l}L</StChip>
                <span style={{ color: theme.textMuted, marginLeft: 2, letterSpacing: -0.1 }}>
                  {row.gf}:{row.ga}
                  <span style={{
                    marginLeft: 6, fontWeight: 700,
                    color: gd > 0 ? theme.accent : gd < 0 ? theme.loss : theme.textMuted,
                  }}>{gd > 0 ? '+' : ''}{gd}</span>
                </span>
              </div>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{
                fontSize: 24, fontWeight: 800, letterSpacing: -0.7,
                color: isMe ? theme.accent : theme.text,
                fontVariantNumeric: 'tabular-nums', lineHeight: '26px',
              }}>{row.pts}</div>
              <div style={{
                fontSize: 9, fontWeight: 700, color: theme.textMuted,
                letterSpacing: 0.6, textTransform: 'uppercase', marginTop: 1,
              }}>pts</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StChip({ children, theme, kind }) {
  const styles = {
    win:  { bg: 'rgba(46,167,106,0.12)',  color: theme.win  },
    loss: { bg: 'rgba(226,90,47,0.12)',   color: theme.loss },
    draw: { bg: 'rgba(20,18,14,0.05)',    color: theme.text },
  };
  const s = styles[kind] || styles.draw;
  return (
    <span style={{
      padding: '2px 6px', borderRadius: 6,
      fontWeight: 700, fontSize: 11,
      background: s.bg, color: s.color,
    }}>{children}</span>
  );
}

function ScheduleList({ team, theme, kind }) {
  const games = team.schedule.filter(g => g.status === kind);
  if (games.length === 0) {
    return (
      <div style={{
        padding: 28, borderRadius: 16, border: `1px dashed ${theme.borderStrong}`,
        textAlign: 'center', color: theme.textMuted, fontSize: 14, background: '#fff',
      }}>
        {kind === 'upcoming' ? 'No upcoming matches.' : 'No results yet.'}
      </div>
    );
  }

  // Group by month
  const groups = {};
  games.forEach(g => {
    const d = new Date(g.date + 'T00:00:00');
    const k = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    (groups[k] = groups[k] || []).push(g);
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {Object.entries(groups).map(([month, list]) => (
        <div key={month}>
          <div style={{
            fontSize: 11, fontWeight: 700, color: theme.textMuted,
            letterSpacing: 0.4, textTransform: 'uppercase',
            paddingLeft: 6, marginBottom: 8,
          }}>{month}</div>
          <div style={{
            background: '#fff', borderRadius: 16,
            border: `1px solid ${theme.border}`, overflow: 'hidden',
          }}>
            {list.map((g, i) => <GameRow key={g.id} game={g} team={team} theme={theme} last={i === list.length - 1} />)}
          </div>
        </div>
      ))}
    </div>
  );
}

function GameRow({ game, team, theme, last }) {
  const isHome = game.home === team.name;
  const opp = isHome ? game.away : game.home;
  const d = new Date(game.date + 'T00:00:00');
  const day = d.toLocaleDateString('en-US', { weekday: 'short' });
  const dayNum = d.getDate();

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 14px',
      borderBottom: last ? 'none' : `1px solid ${theme.border}`,
    }}>
      {/* date block */}
      <div style={{
        width: 44, textAlign: 'center', flexShrink: 0,
      }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: theme.textMuted, letterSpacing: 0.4, textTransform: 'uppercase' }}>{day}</div>
        <div style={{ fontSize: 20, fontWeight: 800, lineHeight: '22px', color: theme.text, fontVariantNumeric: 'tabular-nums' }}>{dayNum}</div>
      </div>

      <div style={{ width: 1, alignSelf: 'stretch', background: theme.border }}/>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, color: theme.textMuted,
            background: 'rgba(20,18,14,0.05)', padding: '2px 5px', borderRadius: 4,
            letterSpacing: 0.4, textTransform: 'uppercase',
          }}>{isHome ? 'Home' : 'Away'}</span>
          <span style={{ fontSize: 12, color: theme.textMuted, fontVariantNumeric: 'tabular-nums' }}>{game.time}</span>
        </div>
        <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: -0.2, marginTop: 3, color: theme.text }}>
          {isHome ? 'vs' : '@'} {opp}
        </div>
        <div style={{ fontSize: 12, color: theme.textMuted, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {game.venue}
        </div>
      </div>

      {game.status === 'final' ? (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0,
        }}>
          <FormChip result={game.result} size={22} theme={theme} />
          <div style={{
            fontSize: 14, fontWeight: 700, color: theme.text, fontVariantNumeric: 'tabular-nums',
            letterSpacing: -0.2,
          }}>
            {isHome ? `${game.hs}–${game.as}` : `${game.as}–${game.hs}`}
          </div>
        </div>
      ) : (
        <div style={{
          fontSize: 11, fontWeight: 700, color: theme.accent,
          background: theme.accentTint, padding: '5px 9px', borderRadius: 8,
          letterSpacing: 0.3, textTransform: 'uppercase', flexShrink: 0,
        }}>
          Upcoming
        </div>
      )}
    </div>
  );
}

Object.assign(window, { MyTeamsScreen, TeamDetailScreen });
