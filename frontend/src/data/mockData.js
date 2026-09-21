export const schema = {
  tables: [
    {
      name: "customers",
      rowCount: 4820,
      columns: [
        { name: "customer_id", type: "integer", pk: true },
        { name: "first_name", type: "varchar" },
        { name: "last_name", type: "varchar" },
        { name: "email", type: "varchar" },
        { name: "country", type: "varchar" },
        { name: "signup_date", type: "date" },
      ],
    },
    {
      name: "orders",
      rowCount: 18230,
      columns: [
        { name: "order_id", type: "integer", pk: true },
        { name: "customer_id", type: "integer", fk: "customers.customer_id" },
        { name: "order_date", type: "date" },
        { name: "status", type: "varchar" },
      ],
    },
    {
      name: "order_items",
      rowCount: 51940,
      columns: [
        { name: "order_item_id", type: "integer", pk: true },
        { name: "order_id", type: "integer", fk: "orders.order_id" },
        { name: "product_id", type: "integer", fk: "products.product_id" },
        { name: "quantity", type: "integer" },
        { name: "unit_price", type: "numeric" },
      ],
    },
    {
      name: "products",
      rowCount: 612,
      columns: [
        { name: "product_id", type: "integer", pk: true },
        { name: "product_name", type: "varchar" },
        { name: "category", type: "varchar" },
        { name: "price", type: "numeric" },
      ],
    },
  ],
  relationships: [
    { from: "orders", to: "customers", label: "customer_id" },
    { from: "order_items", to: "orders", label: "order_id" },
    { from: "order_items", to: "products", label: "product_id" },
  ],
};

export const suggestedQuestions = [
  "How many new customers signed up last month?",
  "What were our top 10 products?",
  "Which region generated the most revenue?",
  "Show customers whose spending increased this quarter.",
];

export const clarificationOptions = [
  {
    id: "spending",
    icon: "dollar",
    label: "Highest spending",
    description: "Customers with the highest total purchase value.",
  },
  {
    id: "orders",
    icon: "trending",
    label: "Most orders",
    description: "Customers who placed the most orders.",
  },
  {
    id: "aov",
    icon: "target",
    label: "Highest average order",
    description: "Customers with the highest average transaction value.",
  },
];

export const pipelineStagesInitial = [
  "Understanding request",
  "Mapping business terminology",
  "Detecting ambiguity",
];

export const pipelineStagesAfterClarification = [
  "Intent resolved",
  "Building query plan",
  "Generating SQL",
  "Validating query",
  "Executing",
];

export const demoSql = {
  spending: `SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name AS name,
    SUM(oi.quantity * oi.unit_price) AS total_spending
FROM customers c
JOIN orders o
    ON c.customer_id = o.customer_id
JOIN order_items oi
    ON oi.order_id = o.order_id
WHERE o.order_date >= date_trunc('month', now()) - interval '1 month'
  AND o.order_date < date_trunc('month', now())
GROUP BY c.customer_id, name
ORDER BY total_spending DESC
LIMIT 10;`,
  orders: `SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name AS name,
    COUNT(o.order_id) AS order_count
FROM customers c
JOIN orders o
    ON c.customer_id = o.customer_id
WHERE o.order_date >= date_trunc('month', now()) - interval '1 month'
  AND o.order_date < date_trunc('month', now())
GROUP BY c.customer_id, name
ORDER BY order_count DESC
LIMIT 10;`,
  aov: `SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name AS name,
    AVG(o.order_total) AS avg_order_value
FROM customers c
JOIN (
    SELECT order_id, customer_id, SUM(quantity * unit_price) AS order_total
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    GROUP BY order_id, customer_id
) o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, name
ORDER BY avg_order_value DESC
LIMIT 10;`,
  products: `SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM products p
JOIN order_items oi
    ON oi.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category
ORDER BY revenue DESC
LIMIT 10;`,
  region: `SELECT
    c.country,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM customers c
JOIN orders o
    ON o.customer_id = c.customer_id
JOIN order_items oi
    ON oi.order_id = o.order_id
GROUP BY c.country
ORDER BY revenue DESC;`,
  revenue: `SELECT
    date_trunc('month', o.order_date) AS month,
    SUM(oi.quantity * oi.unit_price) AS revenue
FROM orders o
JOIN order_items oi
    ON oi.order_id = o.order_id
WHERE o.order_date >= now() - interval '6 months'
GROUP BY month
ORDER BY month;`,
  signups: `SELECT
    date_trunc('week', signup_date) AS week,
    COUNT(*) AS new_customers
FROM customers
WHERE signup_date >= date_trunc('month', now()) - interval '1 month'
  AND signup_date < date_trunc('month', now())
GROUP BY week
ORDER BY week;`,
};

const names = [
  "Ava Whitfield", "Marcus Chen", "Priya Nair", "Elena Petrova", "Noah Kim",
  "Isabelle Laurent", "Diego Alvarez", "Grace Osei", "Yuki Tanaka", "Liam O'Connor",
];

const productNames = [
  { name: "Aurora Wireless Headphones", category: "Electronics" },
  { name: "Nimbus Standing Desk", category: "Furniture" },
  { name: "Solace Weighted Blanket", category: "Home" },
  { name: "Pulse Fitness Tracker", category: "Electronics" },
  { name: "Drift Ceramic Mug Set", category: "Kitchen" },
  { name: "Echo Bluetooth Speaker", category: "Electronics" },
  { name: "Haven Memory Foam Pillow", category: "Home" },
  { name: "Cascade Water Bottle", category: "Outdoor" },
  { name: "Lumen Desk Lamp", category: "Furniture" },
  { name: "Orbit Phone Stand", category: "Electronics" },
];

export const revenueByMonth = [
  { month: "Apr", revenue: 82000 },
  { month: "May", revenue: 91500 },
  { month: "Jun", revenue: 87200 },
  { month: "Jul", revenue: 104800 },
  { month: "Aug", revenue: 118300 },
  { month: "Sep", revenue: 126900 },
];

export const customersByCountry = [
  { country: "USA", customers: 1820 },
  { country: "India", customers: 1140 },
  { country: "UK", customers: 640 },
  { country: "Germany", customers: 480 },
  { country: "Canada", customers: 390 },
];

const revenueByRegion = [
  { country: "USA", revenue: 412500 },
  { country: "UK", revenue: 198200 },
  { country: "India", revenue: 176900 },
  { country: "Germany", revenue: 134700 },
  { country: "Canada", revenue: 98300 },
];

const signupsByWeek = [
  { week: "Week 1", new_customers: 84 },
  { week: "Week 2", new_customers: 112 },
  { week: "Week 3", new_customers: 97 },
  { week: "Week 4", new_customers: 131 },
];

export const demoResults = {
  spending: names.map((name, i) => ({
    customer_id: 1000 + i,
    name,
    total_spending: Math.round(9800 - i * 640 + Math.random() * 120),
  })),
  orders: names.map((name, i) => ({
    customer_id: 1000 + i,
    name,
    order_count: Math.round(42 - i * 3 + Math.random() * 2),
  })),
  aov: names.map((name, i) => ({
    customer_id: 1000 + i,
    name,
    avg_order_value: Math.round((610 - i * 34 + Math.random() * 10) * 100) / 100,
  })),
  products: productNames.map((p, i) => ({
    product_id: 2000 + i,
    product_name: p.name,
    category: p.category,
    revenue: Math.round(48000 - i * 3600 + Math.random() * 800),
  })),
  region: revenueByRegion,
  revenue: revenueByMonth,
  signups: signupsByWeek,
};

export const queryHistory = [
  {
    id: "q-1042",
    question: "Show me last month's best customers",
    resolved: "Highest total spending",
    status: "success",
    executedAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
    durationMs: 182,
  },
  {
    id: "q-1041",
    question: "What were our top 10 products by revenue?",
    resolved: null,
    status: "success",
    executedAt: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
    durationMs: 145,
  },
  {
    id: "q-1040",
    question: "Delete inactive customers",
    resolved: null,
    status: "clarification",
    executedAt: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
    durationMs: null,
  },
  {
    id: "q-1039",
    question: "Which region generated the most revenue this quarter?",
    resolved: null,
    status: "success",
    executedAt: new Date(Date.now() - 1000 * 60 * 60 * 50).toISOString(),
    durationMs: 211,
  },
  {
    id: "q-1038",
    question: "Show orders from a customer that doesn't exist",
    resolved: null,
    status: "failed",
    executedAt: new Date(Date.now() - 1000 * 60 * 60 * 72).toISOString(),
    durationMs: 64,
  },
];

export const architectureSteps = [
  { key: "question", label: "User Question", detail: "The raw natural-language question, exactly as typed." },
  { key: "intent", label: "Intent Extractor", detail: "An LLM maps the question onto tables, columns, filters, and aggregations." },
  { key: "ambiguity", label: "Ambiguity Engine", detail: "Checks the intent against the live schema for missing filters, unclear joins, and vague terms." },
  { key: "clarification", label: "Clarification", detail: "If something's genuinely unclear, QueryMind asks — instead of guessing." },
  { key: "resolved", label: "Resolved Intent", detail: "The intent, now unambiguous, with the user's choice folded back in." },
  { key: "planner", label: "Query Planner", detail: "Decides join order, base table, and clause structure." },
  { key: "generator", label: "SQL Generator", detail: "Builds parameterized SQL — never string-interpolated values." },
  { key: "validator", label: "SQL Validator", detail: "A hardcoded safety net blocks unfiltered writes even if upstream checks are bypassed." },
  { key: "database", label: "Database", detail: "The query runs against your actual schema, read-only by default." },
  { key: "result", label: "Result Interpreter", detail: "Rows come back shaped into tables, charts, and plain-language summaries." },
];

export const trustPoints = [
  { title: "Read-only by default", detail: "Every generated query runs in a read-only mode unless a workspace explicitly enables writes." },
  { title: "Schema-aware generation", detail: "SQL is only ever built from tables and columns that actually exist in your connected database." },
  { title: "No unfiltered writes", detail: "DELETE and UPDATE statements without a WHERE clause are blocked before execution, not after." },
  { title: "Query auditing", detail: "Every generated statement, its parameters, and its outcome are logged for review." },
  { title: "Encrypted credentials", detail: "Database credentials are encrypted at rest and never exposed to the browser." },
  { title: "Controlled access", detail: "Per-workspace permissions decide which tables and operations a user can reach." },
];
