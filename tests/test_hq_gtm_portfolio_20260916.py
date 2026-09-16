from scripts.hq_gtm_portfolio_20260916 import MARK, HEADERS, transform


def sample_board():
    return '''<!doctype html><html><body><div class="wrap">
<h2><span class="k">Sorted by how big this can get, not by pillar &middot; column titles repeat in every tier</span>The portfolio</h2>
<table><thead><tr><th>#</th><th>STREAM</th><th>DOMAIN</th><th>PRICE</th></tr></thead><tbody>
<tr><td class="tier" colspan="4">TIER</td></tr>
<tr><td class="id">4.1</td><td>ChamDigital Swiss websites</td><td>chamdigital.ch</td><td>CHF 1,500</td></tr>
<tr><td class="id">3.1</td><td>Unknown future initiative</td><td>example.test</td><td>—</td></tr>
</tbody></table>
<h2>Other section</h2><p>preserve me</p>
</div></body></html>'''


def test_adds_gtm_columns_and_strategy_without_inventing_funnel():
    out = transform(sample_board())
    assert MARK in out
    assert "GTM<br>PRIORITY" in out
    assert "Owner-led 10/day high-fit local SME" in out
    assert "measure in LeadMine" in out
    assert "Get stranger #1" in out
    assert "preserve me" in out
    assert f'colspan="{4 + len(HEADERS)}"' in out


def test_unknown_initiative_stays_unmeasured():
    out = transform(sample_board())
    assert "rank when buyer/channel is defined" in out
    assert "Define buyer + first proof" in out


def test_transform_is_idempotent():
    once = transform(sample_board())
    twice = transform(once)
    assert twice == once
