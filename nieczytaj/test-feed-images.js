'use strict';
// Publisher RSS formats -> parsed articles -> real country homepage, without network calls.
const assert = require('node:assert/strict');
const { server, state, fetchFeed, rebuildCountryEditions, tenantFromHost, feedsFor } = require('./server');
const request = require('./request-fixture');
const originalFetch = global.fetch;
const ns = 'http://search.yahoo.com/mrss/';
const small = 'https://images.example.at/story-150.jpg';
const large = 'https://images.example.at/story-800.jpg';
const description = 'Das Parlament hat neue Regeln beschlossen. Die Umsetzung beginnt im Oktober.';
const date = new Date().toUTCString();
const item = (media, desc = '', title = 'Österreich Parlament beschliesst neue Regeln') => `<item>
  <title>${title}</title><link>https://news.example.at/story</link><pubDate>${date}</pubDate>
  <description>${desc}</description>${media}</item>`;
async function parse(xml, id = 'standard') {
  const feed = feedsFor(tenantFromHost('liesnicht.at')).find(f => f.id === id);
  global.fetch = async () => ({ ok: true, text: async () => `<rss><channel>${xml}</channel></rss>` });
  return fetchFeed({ ...feed });
}
(async () => {
  try {
    // Actual DER STANDARD structure: escaped HTML and default-namespace Media RSS variants.
    const standard = await parse(item(`<group xmlns="${ns}"><content width="150" url="${small}"/><content width="800" url="${large}"/><credit>Photo credit</credit></group><content width="150" url="${small}" xmlns="${ns}"/>`, `&lt;img src="${small}"&gt;${description}`));
    assert.equal(standard[0].img, large, 'prefer the publisher-provided 800px image over its tiny thumbnail');
    assert.equal(standard[0].desc, description, 'strip embedded markup from the readable description');

    const encoded = await parse(item('', `&lt;img src='https://images.example.at/encoded.jpg?a=1&amp;amp;b=2'&gt;${description}`));
    assert.equal(encoded[0].img, 'https://images.example.at/encoded.jpg?a=1&b=2');
    const single = await parse(item(`<content xmlns='${ns}' url='${large}'/>`));
    assert.equal(single[0].img, large, 'default namespace on a standalone element');
    const enclosure = await parse(item(`<enclosure type='image/jpeg' url='${large}'/>`));
    assert.equal(enclosure[0].img, large, 'image enclosure supports either quote style');
    const media = await parse(item(`<media:content type="video/mp4" width="1920" url="https://images.example.at/video.mp4"/><media:thumbnail width="800" url="${large}"/>`));
    assert.equal(media[0].img, large, 'video must not displace a usable thumbnail');
    const cdata = await parse(item('', `<![CDATA[<img src="${large}">${description}]]>`));
    assert.equal(cdata[0].img, large, 'CDATA images remain supported');
    const unsafe = await parse(item(`<media:thumbnail url="javascript:alert(1)"/><content xmlns="${ns}" url="data:image/svg+xml,bad"/>`));
    assert.equal(unsafe[0].img, '', 'only HTTP(S) publisher image URLs are rendered');

    const orf = await parse(item('', ''), 'orf');
    assert.equal(orf[0].img, '', 'image-free ORF items remain valid articles');
    orf[0].at += 1000; // The lead may have no photo/description while a co-covering source does.
    const now = Date.now();
    state.feedCache = { standard: { ok: true, at: now, items: standard }, orf: { ok: true, at: now, items: orf } };
    state.lastRefresh = now;
    rebuildCountryEditions(now);
    const home = (await request(server, 'www.liesnicht.at', '/')).body;
    assert.ok(home.includes(`src="${large}"`), 'the image reaches the Austrian homepage');
    assert.ok(home.includes(description), 'publisher text fills the card when no AI summary exists');
    assert.match(home, /class="excerpt-source"[^>]*>DER STANDARD<\/a>/, 'the description names its actual publisher');
    assert.ok(!home.includes('class="timg noimg"'), 'no empty branded image blocks');
    assert.ok(!home.includes('KI kurzgefasst'), 'publisher text is not labelled as an AI summary');

    // If no publisher has an image, use a compact text card and keep the headline accessible.
    delete state.feedCache.standard;
    rebuildCountryEditions(now);
    const noImage = (await request(server, 'www.liesnicht.at', '/')).body;
    assert.ok(noImage.includes('class="tile hero text-only"'));
    assert.ok(noImage.includes(orf[0].title));
    assert.ok(!noImage.includes('class="timg'));
    assert.ok(!noImage.includes('undefined'));

    // A publisher may later remove an image; the shipped handler removes its box and row span.
    const onError = home.match(/<img[^>]+onerror="([^"]+)"/)[1];
    let removed = false, compact = false;
    new Function(onError).call({
      closest: () => ({ classList: { add: name => { compact = name === 'text-only'; } } }),
      parentNode: { remove: () => { removed = true; } },
    });
    assert.ok(removed && compact, 'broken image cards also collapse into the text layout');
    console.log('Publisher image parsing and missing-image homepage checks passed');
  } finally { global.fetch = originalFetch; }
})().catch(error => { console.error(error); process.exitCode = 1; });
