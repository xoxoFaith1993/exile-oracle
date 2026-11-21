"""Background job: find the launch hour of the last 3 PoE 2 leagues on GGG's public Currency Exchange history and
pull their first 7 days (polite: one page every 1.5 s, resumable). Log: F:\\PoE2Toolkit\\logs\\leaguestart.log

    python leaguestart_pull.py"""

import datetime
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poe2kit import config, db, leaguestart as ls  # noqa: E402

LOG = os.path.join(config.LOG_DIR, 'leaguestart.log')
# (league, a time before it existed, a time during it)
SEARCH = [('Fate of the Vaal', datetime.datetime(2025, 12, 1), datetime.datetime(2026, 3, 15)),
          ('Runes of Aldur', datetime.datetime(2026, 5, 23, 18), datetime.datetime(2026, 8, 1, 18)),
          ('Forbidden Rites', datetime.datetime(2026, 8, 1, 18), datetime.datetime(2026, 9, 15, 18))]


def main():
    logging.basicConfig(filename=LOG, level=logging.INFO, format='%(asctime)s %(message)s')
    log = logging.info
    con = db.connect()
    ls._setup(con)
    for league, lo, hi in SEARCH:
        row = con.execute('SELECT start_hour FROM ls_league WHERE league=?', (league,)).fetchone()
        if row:
            start = row[0]
        else:
            if ls._count(con, int(lo.timestamp()), league) >= 30:
                log(f'{league}: already live at the lower bound {lo}; widen the search')
                continue
            start = ls.find_start(con, league, int(lo.timestamp()), int(hi.timestamp()))
        log(f'{league}: starts {datetime.datetime.fromtimestamp(start)}')
        ls.pull(con, league, start, log=log)
        log(f'{league}: done')
    log('ALL DONE')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.exception('failed')
        raise
