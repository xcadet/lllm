"""
Sample datasets used across tutorial notebooks.
"""

SAMPLE_PRODUCTS = [
    {
        "id": "p001",
        "name": "Wireless Noise-Canceling Headphones",
        "category": "Electronics",
        "price": 299.99,
        "rating": 4.5,
        "reviews": 1842,
        "description": "Premium over-ear headphones with 30h battery and active noise cancellation.",
    },
    {
        "id": "p002",
        "name": "Mechanical Keyboard TKL",
        "category": "Electronics",
        "price": 149.00,
        "rating": 4.7,
        "reviews": 612,
        "description": "Tenkeyless mechanical keyboard with Cherry MX Brown switches and RGB backlight.",
    },
    {
        "id": "p003",
        "name": "Ergonomic Office Chair",
        "category": "Furniture",
        "price": 489.00,
        "rating": 4.3,
        "reviews": 923,
        "description": "Lumbar-supported mesh chair with adjustable armrests and 5-year warranty.",
    },
    {
        "id": "p004",
        "name": "Stainless Steel Water Bottle 32oz",
        "category": "Kitchen",
        "price": 34.95,
        "rating": 4.8,
        "reviews": 5210,
        "description": "Double-walled vacuum insulation keeps drinks cold 24h, hot 12h.",
    },
    {
        "id": "p005",
        "name": "Python Programming: From Novice to Expert",
        "category": "Books",
        "price": 49.99,
        "rating": 4.6,
        "reviews": 3301,
        "description": "Comprehensive 800-page guide covering Python 3.12 with hands-on projects.",
    },
]

SAMPLE_REVIEWS = [
    {
        "product_id": "p001",
        "reviewer": "alice_w",
        "rating": 5,
        "text": "Absolutely love these headphones. The noise cancellation is top-tier and battery life is incredible.",
    },
    {
        "product_id": "p001",
        "reviewer": "bob_k",
        "rating": 3,
        "text": "Sound quality is good but they feel tight after long sessions. Also the app crashes sometimes.",
    },
    {
        "product_id": "p002",
        "reviewer": "charlie_m",
        "rating": 5,
        "text": "Best keyboard I've ever used. The tactile feedback is satisfying and build quality is superb.",
    },
    {
        "product_id": "p003",
        "reviewer": "diana_l",
        "rating": 4,
        "text": "Very comfortable for long work sessions. Assembly was a bit tricky but instructions were clear.",
    },
    {
        "product_id": "p004",
        "reviewer": "evan_r",
        "rating": 5,
        "text": "My ice is still there after 24 hours! The lid seals perfectly and no leaks.",
    },
]

SAMPLE_TASKS = [
    "Summarize the Q3 earnings report and highlight key risks.",
    "Draft a follow-up email to a client who requested a product demo.",
    "Write three alternative taglines for a new productivity app.",
    "Classify the sentiment of each product review as positive, neutral, or negative.",
    "Convert the following JSON schema to a Markdown table.",
]
