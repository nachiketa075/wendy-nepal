// The shop's printed menu, transcribed from CM.pdf (3 pages, supplied 10 Oct 2026)
// and served at /menu/wendy-juice-shop-menu.pdf.
//
// Names, descriptions, prices and add-ons are kept exactly as printed, including
// wording the owner still needs to confirm (see docs/OWNER_CONFIRMATION.md).
// Do not "correct" entries here; change them when the owner confirms.
//
// IDs are stable slugs ("<category>-<item>") so a later database import can keep
// them. The shape mirrors GET /api/menu (categories -> items, price_npr,
// is_available) with two additions the API does not have yet: `addons` on an
// item and `notes` on a category.

export const MENU_SOURCE_DOCUMENT = {
  title: 'Wendy Juice Shop menu',
  file: 'CM.pdf',
  publicPath: '/menu/wendy-juice-shop-menu.pdf',
  pages: 3,
  suppliedOn: '2026-10-10',
}

// [id, name, price, description, addons]
const RAW = [
  {
    slug: 'coffee', name: 'Coffee', page: 1, items: [
      ['espresso', 'Espresso', 150],
      ['doppio', 'Doppio', 170],
      ['americano', 'Americano', 170],
      ['lungo', 'Lungo', 190],
      ['cappuccino', 'Cappuccino', 220],
      ['cafe-latte', 'Cafe Latte', 220],
      ['cafe-mocha', 'Cafe Mocha', 240],
      ['iced-americano', 'Iced Americano', 230],
      ['iced-cappuccino', 'Iced Cappuccino', 280],
      ['iced-latte', 'Iced latte', 280],
      ['iced-mocha', 'Iced Mocha', 280],
      ['flat-white', 'Flat White', 200],
    ],
  },
  {
    slug: 'tea', name: 'Tea', page: 1, items: [
      ['black-tea', 'Black Tea', 50],
      ['lemon-tea', 'Lemon Tea', 70],
      ['milk-tea', 'Milk Tea', 80],
      ['masala-tea', 'Masala Tea', 90],
      ['hot-chocolate', 'Hot chocolate', 190],
      ['ginger-lemon-honey', 'Ginger Lemon Honey', 200],
      ['hot-lemon-honey', 'Hot Lemon Honey', 150],
      ['green-tea', 'Green Tea', 70],
    ],
  },
  {
    slug: 'fresh-juice', name: 'Fresh Juice', page: 1, items: [
      ['banana-lassi', 'Banana lassi', 180],
      ['watermelon', 'Watermelon', 180],
      ['avocado', 'Avocado', 350],
      ['pineapple', 'Pineapple', 350],
      ['papaya', 'Papaya', 180],
      ['orange', 'Orange', 380],
      ['apple', 'Apple', 380],
      ['mango', 'Mango', 300],
      ['abc', 'ABC', 350, '(Apple, Beetroot, Carrot)'],
      ['cucumber', 'Cucumber', 230],
      ['mint-lemonade', 'Mint lemonade', 200],
      ['fresh-lemonade', 'Fresh lemonade', 250],
      ['strawberry-lemonade', 'Strawberry lemonade', 350],
      ['mixed-juice', 'Mixed Juice', 350, '(choose any 3 fruits from above)'],
    ],
  },
  {
    slug: 'lassi-milkshake', name: 'Lassi / Milkshake', page: 1, items: [
      ['banana', 'Banana', 180],
      ['papaya', 'Papaya', 180],
      ['apple', 'Apple', 380],
      ['mango', 'Mango', 300],
    ],
  },
  {
    slug: 'blended-beverages', name: 'Blended Beverages', page: 1, items: [
      ['blended-watermelon-mint', 'Blended Watermelon Mint', 180],
      ['golden-immunity-boost', 'Golden Immunity Boost', 180],
      ['cucumber-lemon-detox', 'Cucumber Lemon Detox', 380],
      ['green-zing', 'Green Zing', 300],
    ],
  },
  {
    slug: 'fruit-bowl', name: 'Fruit Bowl', page: 2, items: [
      ['fruit-salad', 'Fruit Salad', 400, 'Seasonal Fresh Fruits'],
      ['fruit-with-yogurt', 'Fruit with Yogurt', 450, 'Seasonal Fruits, Plain Yogurt'],
      ['muesli-fruit-yogurt', 'Muesli Fruit Yogurt', 480, 'Muesli, Seasonal Fruits, Yogurt'],
      ['granola-fruit-yogurt', 'Granola Fruit Yogurt', 480, 'Granola, Seasonal Fruits, Yogurt'],
      ['porridge-with-fruit', 'Porridge with Fruit', 400, 'Oat Porridge, Seasonal Fruits'],
      ['oats-with-fruit', 'Oats with Fruit', 400, 'Rolled Oats, Seasonal Fruits'],
    ],
  },
  {
    slug: 'salad', name: 'Salad', page: 2, items: [
      ['avocado-salad', 'Avocado Salad', 400,
        '(Avocado, cheese, lettuce, rucola, kale, carrot, tomato, olive, cabbage, dressed with honey mustard sauce)'],
      ['green-harvest-salad', 'Green Harvest Salad', 400,
        '(feta cheese, mixed lettuce, rucola, kale, carrot, apple, pomegranate, grapes, dressed with honey mustard sauce, garnished with microgreens and basils)'],
      ['chicken-caesar-salad', 'Chicken Caesar Salad', 400, '(chicken, mozzarella cheese, mixed lettuce, olive)'],
    ],
  },
  {
    slug: 'smoothie', name: 'Smoothie', page: 2, items: [
      ['sunrise-smoothie', 'Sunrise Smoothie', 200, '(Banana, Strawberry, Beetroot, Orange juice)'],
      ['matcha-muse', 'Matcha Muse', 250, '(Match Powder, Avocado, Dates, Spinach, Almond Milk)'],
      ['super-green-boost', 'Super green Boost', 250, '(Spinach, Spirulina, Hempseed, Banana, Apple juice)'],
      ['banananut-smoothie', 'Banananut Smoothie', 250, '(Banana, Peanut Butter, Coco Powder, Oat milk)'],
      ['mango-majesty', 'Mango Majesty', 250, '(Mango, Curd, Milk, Sugar)'],
      ['banana-bliss', 'Banana Bliss', 300, '(Banana, Curd, Milk,Almond)'],
    ],
  },
  {
    slug: 'smoothie-bowl', name: 'Smoothie Bowl', page: 2, items: [
      ['papaya-smoothie-bowl', 'Papaya Smoothie Bowl', 480, 'Papaya, Banana, Granola, Coconut'],
      ['mango-smoothie-bowl', 'Mango Smoothie Bowl', 500, 'Mango, Banana, Granola, Honey'],
      ['avocado-smoothie-bowl', 'Avocado Smoothie Bowl', 600, 'Avocado, Banana, Granola, Honey'],
      ['strawberry-smoothie-bowl', 'Strawberry Smoothie Bowl', 550, 'Strawberry, Banana, Granola'],
    ],
  },
  {
    slug: 'brunch', name: 'Brunch', page: 3, items: [
      ['simple-breakfast', 'Simple Breakfast', 450,
        '(Eggs, Toast, Butter, Jam, sautéed potatoes, onions, capsicum, mushrooms, spinach, fruit salad)',
        [{ label: 'add on sausages', price: 80, unit: 'per piece' }]],
      ['vegan-breakfast', 'Vegan Breakfast', 500,
        '(toast, peanut butter, fried tofu, sautéed mushroom, spinach, tomatoes, fruit salad, lettuce, kale, rocket garnished with microgreens and basils, fruit salad)'],
      ['smashed-avocado-on-toast', 'Smashed Avocado on Toast', 500,
        '(Toast, smashed avocado, sautéed mushrooms, tomatoes, spinach, fruit salad, green leafy salad garnished with microgreens and basils)',
        [{ label: 'add on 2 eggs', price: 80 }]],
      ['french-toast', 'French Toast', 450,
        '(Toast coated in cinnamon and egg, drizzled with honey, fresh fruits toppings, garnished with almond, raisin and coconut powder)'],
      ['oatmeal-pancake', 'Oatmeal Pancake', 450,
        '(creamy banana oats made with milk, crowned with fresh fruits and a touch of golden honey)'],
      ['vegan-porridge', 'Vegan Porridge', 450, 'Sourdough Toast, Avocado, Cherry Tomatoes'],
      ['cheese-frittata', 'Cheese Frittata', 500,
        '(fluffy egg frittata loaded with melted cheese, lightly seasoned herbs and fresh vegetables, sausages)',
        [{ label: 'add on 2 eggs', price: 80 }]],
    ],
  },
  {
    slug: 'sandwiches', name: 'Sandwiches', page: 3,
    notes: [{ label: 'Extra Cheese Topping', price: 70, prefix: '+' }],
    items: [
      ['veg-sandwich', 'Veg Sandwich', 200],
      ['cheese-sandwich', 'Cheese Sandwich', 250],
      ['tuna-sandwich', 'Tuna Sandwich', 250],
      ['chicken-sandwich', 'Chicken Sandwich', 250],
      ['egg-sandwich', 'Egg Sandwich', 250],
      ['bacon-sandwich', 'Bacon Sandwich', 300],
      ['ham-sandwich', 'Ham Sandwich', 300],
    ],
  },
  {
    slug: 'buddha-bowl', name: 'Buddha Bowl', page: 3, items: [
      ['vegan-buddha-bowl', 'Vegan Buddha Bowl', 600, '(Seasonal Veggies, Grains, Hummus, Tahini Dressing)'],
      ['chicken-buddha-bowl', 'Chicken Buddha Bowl', 680, '(Grilled Chicken, Grains, Veggies, Tahini Dressing)'],
    ],
  },
  {
    // As printed: the Rice Bowl section repeats the two Buddha Bowl entries.
    slug: 'rice-bowl', name: 'Rice Bowl', page: 3, items: [
      ['vegan-buddha-bowl', 'Vegan Buddha Bowl', 600, '(Seasonal Veggies, Grains, Hummus, Tahini Dressing)'],
      ['chicken-buddha-bowl', 'Chicken Buddha Bowl', 680, '(Grilled Chicken, Grains, Veggies, Tahini Dressing)'],
    ],
  },
]

export const PDF_MENU = {
  categories: RAW.map((category, c) => ({
    id: category.slug,
    slug: category.slug,
    name: category.name,
    tagline: null,
    sort_order: (c + 1) * 10,
    notes: category.notes || [],
    meta: { source: MENU_SOURCE_DOCUMENT.file, page: category.page },
    items: category.items.map(([slug, name, price, description = null, addons = []], i) => ({
      id: `${category.slug}-${slug}`,
      category_id: category.slug,
      name,
      description,
      is_available: true,
      price_npr: price,
      source: 'owner_pdf',
      sort_order: (i + 1) * 10,
      addons,
      meta: { source: MENU_SOURCE_DOCUMENT.file, page: category.page },
    })),
  })),
}
