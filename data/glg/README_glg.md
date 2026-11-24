# Lexus Global Lacrosse Games 2026: men's rosters and schedule

Compiled 2026-11-22 from public announcement pages, read one page at a time. stats.premierlacrosseleague.com was not used.
Event: Dec 8-13, 2026, The St. James, Springfield VA. Olympic Sixes format, sanctioned by World Lacrosse and USA Lacrosse.
Men's nations: USA, Canada, Haudenosaunee, Australia. Women's teams are left out on purpose.

Files: `glg_mens_schedule.csv` (7 games) is used by the app. The 52-player rosters (13 per nation) are loaded into the warehouse (`src.glg_roster`). The build script and raw page copies are kept with the offline data pipeline.

## Sources

| Key | URL | Date | Gives |
|---|---|---|---|
| PLL-NAT | premierlacrosseleague.com/global-lacrosse-games/nations/{us,can,hau,aus}?division=mens | live | names, jersey numbers, Field/Goalie split, coaches |
| PLL-SCHED | premierlacrosseleague.com/global-lacrosse-games/schedule?division=mens | live | the 7 men's games, start-time epochs, stage labels ("Pool Play", "Semifinal 1/2", "Championship") |
| PLL-ART | premierlacrosseleague.com/articles/global-lacrosse-games-roster-breakdown-{usa,canada,haudenosaunee,australia}-men | Oct 29-30 | roster lists, opener times, some PLL teams and colleges |
| PLL-TAV | premierlacrosseleague.com/articles/haudenosaunee-mens-head-coach-john-tavares-on-keys-to-win-global-lacrosse-games | Nov 12 | a 13-man Haudenosaunee roster |
| USAL | usalacrosse.com/magazine/usa-mens-roster-announced-inaugural-global-lacrosse-games | Oct 28 | USA names, college, PLL team |
| USAL-6S | usalacrosse.com/national-teams/mens-sixes | live | USA vs Canada, Dec 8, 5:30 pm |
| LC | lacrosse.ca/lacrosse-canada-announces-mens-and-womens-rosters-for-pll-global-lacrosse-games/ | Oct 28 | Canada names, goalies, coaches |
| LA | lacrosse.com.au/news/2026/10/30/lexus-global-lacrosse-games-men-and-womens-team-announced/ | Oct 30 | Australia roster, but only in the image GLG_Teams.jpg (I read the image myself) |
| HN-ATLAS / HN-PAN | haudenosauneenationals.com Atlas Cup (Oct 20) and Pan-Am Sixes (Sep 22) roster posts | 2026 | NLL/PLL/college affiliations. These are **different events**, used only for affiliations |
| WL-RULES | worldlacrosse.sport/wp-content/uploads/2026/05/26-28-Sixes-Rule-Book_v2_0526.pdf | May 2026 | Sixes playing rules |

Pages that failed or had nothing: insidelacrosse.com (the fetch was blocked), nll.com/news (no GLG items), haudenosauneenationals.com (no GLG roster post), the PLL news tag/glg page (videos only). PLL matchup pages returned 404.

## Roster verification

| Nation | Count | Sources that agree on all 13 names | Status |
|---|---|---|---|
| USA | 13 (11 field, 2 G) | PLL-NAT, USAL, PLL-ART | **Verified, 3 sources** (USAL calls it a "13-player U.S. roster") |
| Canada | 13 (11 field, 2 G) | PLL-NAT, LC, PLL-ART | **Verified, 3 sources, one of them independent** |
| Australia | 13 (11 field, 2 G) | PLL-NAT, LA graphic, PLL-ART | **Verified, 3 sources, one of them independent** |
| Haudenosaunee | 13 (11 field, 2 G) | PLL-NAT, PLL-ART, PLL-TAV (names 9 players and says "13 members") | **2 sources, both PLL.** No independent Haudenosaunee Nationals or NLL post was found |

Disagreements and flags:
- **Weisshaar (USA):** "Michael" on PLL-NAT, "Mikey" in USAL and PLL-ART. Same player. The CSV uses Michael.
- **Sunday (HAU):** "Tyrsen" on PLL-NAT, "Trysen" in PLL-ART, PLL-TAV and both HN posts. The CSV uses Trysen (4 sources to 1).
- **Heuston (AUS):** "Matt" on PLL-NAT and in the LA graphic, "Marcus" in PLL-ART (probably a typo). The CSV uses Matt.
- **Parsons-Quintiao (AUS):** hyphenated in the LA graphic and PLL-ART, unhyphenated on PLL-NAT. The CSV uses the hyphen.
- **Nonkon Thompson (HAU)** appears as "Shonwahnonkon Thompson" in HN-PAN, wearing #91 in both. I am treating them as the same player; this is inferred, not stated.
- **Jersey numbers come only from PLL-NAT.** Sunday wore #88 in the HN posts but is #83 at the GLG, where Piseno has #88.
- **Positions:** no source gives attack, midfield, defense or FOGO. The CSV has only the field/goalie split from PLL-NAT. Sixes has no specialty positions and no faceoff man (play restarts with a center draw).
- **Alternates:** no source names alternates or reserves, so `is_alternate` is False for everyone.
- **pro_teams / college:** filled only where a source says so. USA teams and colleges come from USAL; the PLL team cities are mapped to club names (Boston = Cannons, New York = Atlas, California = Redwoods, Carolina = Chaos, Denver = Outlaws, Philadelphia = Waterdogs). Canada and Australia affiliations come from PLL-ART, and Wertheim has draft rights only. Haudenosaunee NLL teams come from the HN posts of Sep and Oct 2026, so they may be out of date for the 2026-27 NLL season. Many Canada, Australia and Haudenosaunee rows are left blank rather than filled from memory.
- **Coaches** (not in the CSV): USA Andy Shay (HC) and Tony Resch; Canada Eddie Comeau (HC) and Brodie Merrill; Haudenosaunee John Tavares (HC) and Darris Kilgour; Australia Adam Sear (HC) and Glenn Morley.

## Schedule

- PLL-SCHED gives 7 men's games: 4 "Pool Play", 2 semifinals and 1 championship. Times are ET (EST), converted from the page's embedded epoch times.
- PLL-ART and USAL-6S independently confirm two of them: USA-Canada on Tue Dec 8 at 5:30 pm and Haudenosaunee-Australia on Dec 8 at 7:30 pm.
- The home/away order is PLL's data order (homeTeam/awayTeam). The ticketing page lists the same games in the reverse order ("CAN vs. USA"), so treat home/away as nominal at a neutral site.
- **Uncertain:** pool play has only 4 games, so each team plays 2 of its 3 possible opponents. How semifinal seeding works is not published; the semis are listed as TBD. There is **no 3rd-place or placement game** on the men's schedule.

## Rules

No GLG-specific rules page was found; the PLL site's "What is Olympic Sixes?" FAQ answer is not in the page HTML. The event says it is played "under Olympic Sixes rules" (LA, LC). The points below come from the World Lacrosse 2026-28 Sixes Rule Book:
- 6 per side: 5 field players and 1 goalkeeper. The field is 70 m x 36 m.
- Four 8-minute quarters, with 2-minute breaks between quarters and a 5-minute half-time.
- 30-second shot clock.
- Overtime: tied games go to full 3-minute overtime periods of stopped time, with a 2-minute break before each, repeated until there is a winner. It is **not sudden death**: the team leading at the end of an overtime period wins.
- Center draw at the start of each quarter and overtime period. After a goal, the goalie restarts play from the crease within 5 seconds; there is no faceoff.
- Penalties: a minor foul is a 30-second suspension (or a turnover), a major foul is 1 minute, and 3 majors means a player fouls out. Each team gets one 60-second timeout per half.
- **There are no 2-point goals** (the user confirmed this; the rule book has no 2-point provision).
- **Roster size conflict:** the WL rule book caps active rosters at 12, but all four GLG rosters list 13 (USAL and PLL-TAV both say 13). Either the GLG modifies this rule, or one player per team sits out each game (the eligible list is set 20 minutes before the game). This is unresolved.
