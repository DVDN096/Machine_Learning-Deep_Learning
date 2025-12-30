# utils/categorize.py
def categorize(description):
    """Simple rule-based categorizer - extend rules as needed."""
    if description is None:
        return "🔹 Others"
    desc = str(description).lower()

    if any(word in desc for word in ["zomato", "swiggy", "restaurant", "food", "pizza", "coffee", "cafe"]):
        return "🍔 Food & Dining"
    if any(word in desc for word in ["uber", "ola", "taxi", "petrol", "fuel", "bus", "train", "flight"]):
        return "🚗 Transport"
    if any(word in desc for word in ["amazon", "flipkart", "myntra", "shopping", "mall", "order", "purchase"]):
        return "🛍️ Shopping"
    if any(word in desc for word in ["rent", "electricity", "power", "water", "internet", "phone", "mobile", "bill"]):
        return "🏠 Utilities & Rent"
    if any(word in desc for word in ["salary", "pay", "credited", "deposit", "income"]):
        return "💼 Income"
    if any(word in desc for word in ["mutual", "sip", "investment", "stock", "dividend", "crypto"]):
        return "📈 Investments"
    return "🔹 Others"
