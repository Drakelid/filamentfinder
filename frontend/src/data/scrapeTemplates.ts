import type { CrawlRules, SelectorOverrides } from '../api'

export type ScrapeTemplate = {
  id: string
  name: string
  parser: string
  priority: number
  description: string
  detectionSignals: string[]
  strengths: string[]
  coverage: string[]
  crawlRules?: Partial<CrawlRules>
  selectorOverrides?: Partial<SelectorOverrides>
}

export const SCRAPE_TEMPLATES: ScrapeTemplate[] = [
  {
    id: 'jsonld',
    name: 'JSON-LD Structured Data',
    parser: 'JsonLdParser',
    priority: 100,
    description: 'Use sites that publish schema.org Product markup as the primary source of product, price, currency, SKU, GTIN, and stock data.',
    detectionSignals: ['application/ld+json', 'schema.org/Product', 'offers.priceCurrency'],
    strengths: ['Most reliable parser in the stack', 'Best product detail extraction', 'Works across many storefront engines'],
    coverage: ['Structured product pages', 'Structured listing pages', 'Merchant feeds embedded into HTML'],
    crawlRules: {
      max_pages: 120,
      max_depth: 3,
      same_domain_only: true,
      respect_robots_txt: true,
    },
  },
  {
    id: 'shopify',
    name: 'Shopify Storefront',
    parser: 'ShopifyParser',
    priority: 90,
    description: 'Target Shopify collections and product pages that expose product JSON, collection links, and Shopify-specific pagination.',
    detectionSignals: ['cdn.shopify.com', 'shopify-section', 'myshopify.com', '/products/'],
    strengths: ['Strong collection crawling', 'Variant and compare-at price support', 'Good image and vendor extraction'],
    coverage: ['Native Shopify themes', 'Turbo-style themes', 'Shopify product JSON blocks'],
    crawlRules: {
      max_pages: 150,
      max_depth: 4,
      same_domain_only: true,
      respect_robots_txt: true,
    },
  },
  {
    id: 'woocommerce',
    name: 'WooCommerce',
    parser: 'WooCommerceParser',
    priority: 80,
    description: 'Handle WordPress stores using WooCommerce product markup, price blocks, and loop product cards.',
    detectionSignals: ['wp-content/plugins/woocommerce', 'wc-product', 'woocommerce', '/product/'],
    strengths: ['Strong product card extraction', 'Understands sale vs regular price', 'Useful for medium-complexity catalog sites'],
    coverage: ['WooCommerce product pages', 'WooCommerce archive pages', 'WordPress shop/category routes'],
    crawlRules: {
      max_pages: 120,
      max_depth: 4,
      same_domain_only: true,
      respect_robots_txt: true,
    },
  },
  {
    id: 'magento',
    name: 'Magento',
    parser: 'MagentoParser',
    priority: 70,
    description: 'Cover Magento catalog pages and PDPs using Magento selectors, price-box markup, and pager patterns.',
    detectionSignals: ['Magento_', 'data-mage-init', 'catalog-product-view', 'x-magento-vary'],
    strengths: ['Understands Magento price widgets', 'Good PDP extraction', 'Useful on larger enterprise storefronts'],
    coverage: ['Magento 2 product pages', 'Category listings', 'Enterprise storefront patterns'],
    crawlRules: {
      max_pages: 120,
      max_depth: 4,
      same_domain_only: true,
      respect_robots_txt: true,
    },
  },
  {
    id: 'generic',
    name: 'Generic HTML Heuristics',
    parser: 'GenericParser',
    priority: 0,
    description: 'Fallback parser for sites without clean platform signatures. Uses broad selector heuristics, URL patterns, pagination inference, and Nordic stock language detection.',
    detectionSignals: ['price-like selectors', 'product-card selectors', 'pagination links', 'stock keywords'],
    strengths: ['Catches custom storefronts', 'Handles broad product-card patterns', 'Useful when platform-specific parsers do not match'],
    coverage: ['Custom storefronts', 'Nordic retailer HTML', 'Selector override recovery path'],
    crawlRules: {
      max_pages: 100,
      max_depth: 3,
      same_domain_only: true,
      respect_robots_txt: true,
    },
  },
]

export const GENERIC_HEURISTIC_COVERAGE = [
  '3dnet.no data-product extraction',
  '3DJake-style data-json extraction',
  'Clas Ohlson data-name/data-brand cards',
  'avxperten.no custom product cards',
  'csmegastore.no custom product cards',
  'polyalkemi.no custom product cards',
  'Proshop, Elefun, Computersalg, and Multicom selector packs',
]
