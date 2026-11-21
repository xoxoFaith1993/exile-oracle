"""Several characters (R17): the player's own builds in the vault are their characters; one of them is ACTIVE and
every page (Build Lab, Atlas map mods, the waystone check on Ctrl+D, the farming oracle, Top 1%) follows it.
Stored as settings.active_build; with none picked, the followed in-game plan, else the newest own build."""

from . import config


def characters(con):
    rows = con.execute("SELECT id, label, class, ascendancy, level, main_skill, league FROM build "
                       "WHERE owner='me' ORDER BY id DESC").fetchall()
    from . import mapmods
    active = mapmods.active_build(con)
    out = [{'id': r['id'], 'label': r['label'], 'class': r['class'], 'ascendancy': r['ascendancy'],
            'level': r['level'], 'skill': r['main_skill'], 'league': r['league'], 'active': r['id'] == active}
           for r in rows]
    return {'active': active, 'picked': bool(config.settings().get('active_build')), 'characters': out}


def set_active(con, build_id):
    bid = int(build_id or 0)
    if bid and not con.execute('SELECT 1 FROM build WHERE id=?', (bid,)).fetchone():
        raise ValueError('no such build in the vault')
    config.save_settings({'active_build': bid or None})
    return characters(con)
