/*
  Jill shared orders (REAL DATA from Wardrobe confirmation emails)
  Source: Order confirmations received 2026-01-19

  Stores ONLY: brand, item, size, totals, status, and product URLs.
  NO address, NO email, NO payment info.
*/
(function () {
  'use strict';

  // New key - wipes old mock data
  const ORDERS_LIST_KEY = 'jill_orders_v2';
  const BADGE_KEY = 'jill_badges_v2';

  // Clear old keys on first load
  try {
    localStorage.removeItem('jill_orders_v1');
    localStorage.removeItem('jill_badges_v1');
    localStorage.removeItem('jill_orders_collapse_v1');
  } catch {}

  function safeParse(json, fallback) {
    try { return JSON.parse(json); } catch { return fallback; }
  }

  function loadOrders() {
    return safeParse(localStorage.getItem(ORDERS_LIST_KEY) || '[]', []);
  }

  function saveOrders(list) {
    try { localStorage.setItem(ORDERS_LIST_KEY, JSON.stringify(list)); } catch {}
  }

  function loadBadges() {
    return safeParse(localStorage.getItem(BADGE_KEY) || '{"favorites":0,"orders":0}', { favorites: 0, orders: 0 });
  }

  function saveBadges(b) {
    try { localStorage.setItem(BADGE_KEY, JSON.stringify(b)); } catch {}
  }

  // Seed only if empty
  const existing = loadOrders();
  if (Array.isArray(existing) && existing.length > 0) return;

  const now = Date.now();
  const seeded = [
    // ORDERED (in transit)
    {
      id: 'jk-bundle-2026-01-19',
      kind: 'confirmed',
      active: true,
      brand: 'Jenni Kayne',
      item: 'Brentwood Blazer + Cashmere Cocoon Cardigan',
      size: '2 / XS',
      total: '$765.56',
      status: 'confirmed',
      local_images: ['../wardrobe/images/jenni-kayne-blazer.jpg'],
      product_urls: [
        'https://www.jennikayne.com/products/brentwood-blazer-dark-navy',
        'https://www.jennikayne.com/products/cropped-cashmere-cocoon-cardigan-ivory'
      ],
      updated_at: now
    },
    {
      id: 'barbour-beadnell-2026-01-19',
      kind: 'confirmed',
      active: true,
      brand: 'Barbour',
      item: 'Cropped Beadnell Waxed Jacket',
      size: 'US 6',
      total: '$469.84',
      status: 'confirmed',
      local_images: ['../wardrobe/images/barbour-beadnell.jpg'],
      product_urls: ['https://www.barbour.com/us/cropped-beadnell-waxed-jacket-LWX1403NY92.html'],
      updated_at: now
    },
    {
      id: 'margaux-demi-custom-2026-01-19',
      kind: 'custom_pending',
      active: true,
      brand: 'Margaux',
      item: 'The Demi Ballet Flat (custom)',
      size: '38 (US 8) · Medium',
      total: '$325',
      status: 'confirmed',
      local_images: ['../wardrobe/images/margaux-demi.jpg'],
      details: {
        color: 'Ivory Nappa',
        lining: 'Light Blue',
        monogram: 'JSH'
      },
      product_urls: ['https://margauxny.com/collections/the-demi/products/the-demi-black-navy'],
      updated_at: now
    },
    {
      id: 'ahlem-one-of-one-2026-01-19',
      kind: 'custom_pending',
      active: true,
      brand: 'Ahlem',
      item: 'One of One Bespoke Frames',
      size: '—',
      total: '~$650',
      status: 'confirmed',
      local_images: ['../wardrobe/images/ahlem-custom.jpg'],
      details: {
        program: 'One of One Custom',
        craftsmanship: 'MOF-certified artisan'
      },
      product_urls: ['https://www.ahlemeyewear.com/pages/bespoke-experience'],
      updated_at: now
    },
    // DELIVERED (can return)
    {
      id: 'la-ligne-marin-2026-01-19',
      kind: 'confirmed',
      active: false,
      brand: 'La Ligne',
      item: 'Marin Stripe Sweater',
      size: 'XS',
      total: '$397.93',
      status: 'delivered',
      local_images: ['../wardrobe/images/la-ligne-marin.jpg'],
      product_urls: ['https://lalignenyc.com/products/marin-sweater-cream-navy'],
      updated_at: now
    },
    {
      id: 'sezane-eli-scarf-2026-01-19',
      kind: 'confirmed',
      active: false,
      brand: 'Sézane',
      item: 'Eli Scarf (Navy) + FREE Mon Amour Totebag',
      size: '—',
      total: '$135.98',
      status: 'delivered',
      local_images: ['../wardrobe/images/sezane-scarf.jpg'],
      product_urls: ['https://www.sezane.com/us-en/product/eli-scarf/navy'],
      updated_at: now
    },
    {
      id: 'saint-james-minquidame-2026-01-19',
      kind: 'confirmed',
      active: false,
      brand: 'Saint James',
      item: 'Minquidame Breton Striped Shirt',
      size: '2',
      total: '$97.00',
      status: 'delivered',
      local_images: ['../wardrobe/images/saint-james-breton.jpg'],
      product_urls: ['https://us.saint-james.com/collections/women/products/minquidame-breton-striped-shirt-with-long-sleeve-soft-cotton-women-fit-navy-deep-teal'],
      updated_at: now
    },
    {
      id: 'catbird-threadbare-2026-01-19',
      kind: 'confirmed',
      active: false,
      brand: 'Catbird',
      item: 'Threadbare Ring 14K Gold',
      size: '7',
      total: '$84.01',
      status: 'delivered',
      local_images: ['../wardrobe/images/catbird-threadbare.jpg'],
      product_urls: ['https://www.catbirdnyc.com/threadbare-gold-stacking-ring.html'],
      updated_at: now
    }
  ];

  saveOrders(seeded);

  // Badge: show active orders until opened (both pages clear on open)
  const b = loadBadges();
  b.orders = seeded.filter(o => o.active).length;
  saveBadges(b);
})();
