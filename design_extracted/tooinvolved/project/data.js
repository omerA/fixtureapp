// Mock data for TooInvolved — wired to real NCSA B13B Spring 2026 standings.
// Source: ncsanj.com (scraped 2026-05-12). League is shown as "NCSA B13B Spring 2026".
// User is subscribed to Tenafly SC for the demo.

window.TI_DATA = (() => {
  const leagues = {
    'b13b-ncsa': {
      id: 'b13b-ncsa',
      name: 'NCSA B13B · Spring 2026',
      shortName: 'B13B Spring',
      season: 'Spring 2026 · Week 6',
      ageGroup: 'B13B (U13 Boys)',
      // Ordered by points, then goal difference (matches scraped data)
      standings: [
        { id: 'jerseycity', name: 'JerseyCity FC',    coach: 'Klobe',   crest: '#0F4C8A', mp: 5, w: 5, d: 0, l: 0, gf: 26, ga:  9, pts: 15 },
        { id: 'worldclass', name: 'World Class FC',   coach: 'Hirt',    crest: '#1F1F1F', mp: 5, w: 4, d: 0, l: 1, gf: 15, ga:  7, pts: 12 },
        { id: 'vikings',    name: 'Vikings SC',       coach: 'Adeboye', crest: '#7C1E2D', mp: 6, w: 4, d: 0, l: 2, gf: 19, ga: 13, pts: 12 },
        { id: 'mahwah',     name: 'Mahwah United',    coach: 'Martin',  crest: '#1B7A3E', mp: 6, w: 3, d: 0, l: 3, gf: 15, ga: 16, pts:  9 },
        { id: 'montclair',  name: 'Montclair FC',     coach: 'Ziobro',  crest: '#E9A13B', mp: 6, w: 1, d: 0, l: 5, gf: 12, ga: 26, pts:  3 },
        { id: 'tenafly',    name: 'Tenafly SC',       coach: 'Reiser',  crest: '#2E63B4', mp: 6, w: 0, d: 0, l: 6, gf:  6, ga: 22, pts:  0, subscribed: true },
      ],
    },
  };

  // Tenafly is what the user follows. Form is most-recent-first (left = latest).
  // Schedule below mixes 2 fabricated upcoming fixtures (next 2 Sundays) and
  // the 6 real played games from the scrape.
  const teams = {
    tenafly: {
      id: 'tenafly',
      name: 'Tenafly SC',
      crest: '#2E63B4',
      leagueId: 'b13b-ncsa',
      childName: 'Sam',
      jerseyNumber: 9,
      coach: 'Reiser',
      form: ['L', 'L', 'L', 'L', 'L'], // most recent first
      schedule: [
        // Upcoming (next two Sundays)
        { id: 'g7', date: '2026-05-17', time: '10:00 AM', home: 'Tenafly SC',     away: 'Vikings SC',     venue: 'Tenafly Municipal Field',  status: 'upcoming' },
        { id: 'g8', date: '2026-05-24', time: '11:30 AM', home: 'World Class FC', away: 'Tenafly SC',     venue: 'World Class FC · Field 1', status: 'upcoming' },
        // Played (most recent first)
        { id: 'g6', date: '2026-05-10', time: '11:45 AM', home: 'Tenafly SC',     away: 'JerseyCity FC',  venue: 'Tenafly Municipal Field',  status: 'final', hs: 1, as: 3, result: 'L' },
        { id: 'g5', date: '2026-05-03', time: '03:45 PM', home: 'Tenafly SC',     away: 'Mahwah United',  venue: 'Tenafly Municipal Field',  status: 'final', hs: 1, as: 3, result: 'L' },
        { id: 'g4', date: '2026-05-02', time: '06:00 PM', home: 'World Class FC', away: 'Tenafly SC',     venue: 'World Class FC · Field 1', status: 'final', hs: 5, as: 1, result: 'L' },
        { id: 'g3', date: '2026-04-19', time: '08:00 AM', home: 'Tenafly SC',     away: 'Montclair FC',   venue: 'Tenafly Municipal Field',  status: 'final', hs: 2, as: 3, result: 'L' },
        { id: 'g2', date: '2026-04-12', time: '12:30 PM', home: 'Tenafly SC',     away: 'Vikings SC',     venue: 'Tenafly Municipal Field',  status: 'final', hs: 0, as: 3, result: 'L' },
        { id: 'g1', date: '2026-03-29', time: '10:15 AM', home: 'JerseyCity FC',  away: 'Tenafly SC',     venue: 'JC · Cochrane Caven',      status: 'final', hs: 5, as: 1, result: 'L' },
      ],
    },
  };

  // Search pool for onboarding — all 6 NCSA B13B teams.
  const searchPool = [
    { id: 'tenafly',    name: 'Tenafly SC',       leagueLabel: 'NCSA B13B Spring', city: 'Tenafly, NJ',    coach: 'Reiser'  },
    { id: 'jerseycity', name: 'JerseyCity FC',    leagueLabel: 'NCSA B13B Spring', city: 'Jersey City, NJ', coach: 'Klobe'  },
    { id: 'worldclass', name: 'World Class FC',   leagueLabel: 'NCSA B13B Spring', city: 'New York, NY',    coach: 'Hirt'   },
    { id: 'vikings',    name: 'Vikings SC',       leagueLabel: 'NCSA B13B Spring', city: 'Demarest, NJ',    coach: 'Adeboye'},
    { id: 'mahwah',     name: 'Mahwah United',    leagueLabel: 'NCSA B13B Spring', city: 'Mahwah, NJ',      coach: 'Martin' },
    { id: 'montclair',  name: 'Montclair FC',     leagueLabel: 'NCSA B13B Spring', city: 'Montclair, NJ',   coach: 'Ziobro' },
  ];

  return { leagues, teams, searchPool };
})();
