"""Tests for the object model include/exclude path filter."""

from simplyprint_duet3d.duet.om_filter import ObjectModelFilter


def test_unfiltered_wants_everything():
    """Unfiltered wants everything."""
    f = ObjectModelFilter()
    assert f.include is None
    assert f.wanted("anything")
    assert f.wanted("deeply.nested.path")


def test_match_all_disables_include_filtering():
    """Match all disables include filtering."""
    f = ObjectModelFilter(include=["heat", "*"])
    assert f.include is None
    assert f.wanted("fans")


def test_include_normalization_dedupes_and_collapses_nested():
    """Include normalization dedupes and collapses nested."""
    f = ObjectModelFilter(include=["move.compensation", "move", "heat", "heat"])
    assert f.include == ("move", "heat")


def test_wanted_route_to_at_and_below_include():
    """Wanted route to at and below include."""
    f = ObjectModelFilter(include=["move.compensation"])
    # on the route to the include
    assert f.wanted("move")
    # at the include
    assert f.wanted("move.compensation")
    # below the include
    assert f.wanted("move.compensation.liveGrid")
    # sibling branches are not wanted
    assert not f.wanted("move.axes")
    assert not f.wanted("fans")
    # prefix must match whole path segments
    assert not f.wanted("moveX")


def test_exclude_wins_over_include():
    """Exclude wins over include."""
    f = ObjectModelFilter(include=["job"], exclude=["job.file.thumbnails"])
    assert f.wanted("job.file")
    assert not f.wanted("job.file.thumbnails")
    assert not f.wanted("job.file.thumbnails.0")


def test_exclude_applies_without_include():
    """Exclude applies without include."""
    f = ObjectModelFilter(exclude=["global"])
    assert not f.wanted("global")
    assert f.wanted("state")


def test_refetch_paths_unfiltered_returns_key():
    """Refetch paths unfiltered returns key."""
    f = ObjectModelFilter()
    assert f.refetch_paths("move") == ("move",)


def test_refetch_paths_maps_key_to_included_subtrees():
    """Refetch paths maps key to included subtrees."""
    f = ObjectModelFilter(include=["move.compensation", "heat", "network.name"])
    assert f.refetch_paths("move") == ("move.compensation",)
    assert f.refetch_paths("heat") == ("heat",)
    assert f.refetch_paths("network") == ("network.name",)
    assert f.refetch_paths("fans") == ()
    assert f.refetch_paths("global") == ()


def test_refetch_paths_excluded_key_returns_nothing():
    """Refetch paths excluded key returns nothing."""
    f = ObjectModelFilter(exclude=["global"])
    assert f.refetch_paths("global") == ()


def test_prune_drops_unwanted_branches():
    """Prune drops unwanted branches."""
    f = ObjectModelFilter(include=["move.compensation", "state.status"])
    tree = {
        "move": {"compensation": {"file": "map.csv"}, "axes": [{"pos": 1}]},
        "state": {"status": "idle", "upTime": 100},
        "fans": [{"rpm": 100}],
    }
    assert f.prune(tree) == {
        "move": {"compensation": {"file": "map.csv"}},
        "state": {"status": "idle"},
    }


def test_prune_keeps_lists_atomically():
    """Prune keeps lists atomically."""
    f = ObjectModelFilter(include=["tools"])
    tree = {"tools": [{"heaters": [1], "name": "Hotend"}]}
    assert f.prune(tree) == {"tools": [{"heaters": [1], "name": "Hotend"}]}


def test_prune_respects_exclude_below_include():
    """Prune respects exclude below include."""
    f = ObjectModelFilter(include=["job"], exclude=["job.file.thumbnails"])
    tree = {"job": {"file": {"fileName": "a.gcode", "thumbnails": [{"w": 1}]}}}
    assert f.prune(tree) == {"job": {"file": {"fileName": "a.gcode"}}}


def test_prune_with_path_context():
    """Prune with path context."""
    f = ObjectModelFilter(include=["move.compensation"])
    subtree = {"compensation": {"file": "map.csv"}, "axes": []}
    assert f.prune(subtree, "move") == {"compensation": {"file": "map.csv"}}
