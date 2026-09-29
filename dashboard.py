import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def get_engine():
    """Create and return a SQLAlchemy engine from DATABASE_URL."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("Error: DATABASE_URL not found.")
    
    return create_engine(url)

def store_report(engine):
    """Print counts, the catalog, the top 3 customers, and stretch goals."""
    with engine.connect() as conn:
        # 1. Counts
        users_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        products_count = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
        orders_count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()

        print("--- Store Dashboard")
        print(f"Users: {users_count} | Products: {products_count} | Orders: {orders_count}")

        # 2. Catalog
        print("\nCatalog:")
        catalog = conn.execute(text("SELECT name, price, stock from products ORDER BY name")).fetchall()
        for name, price, stock in catalog:
            print(f'{name:<10} ${price} (currently in stock: {stock})')

        # 3. Top customers
        print("\nTop customers:")
        top_customers = conn.execute(text("""
            SELECT u.email, SUM(o.quantity) as total_orders
            FROM users AS u
            INNER JOIN orders AS o ON o.user_id = u.id
            GROUP BY u.email
            ORDER BY total_orders DESС
            LIMIT 3""")).fetchall()
        
        for email, total_items in top_customers:
            print(f"{email:<10} - {total_items} {"item" if total_items == 1 else "items"}")
        
        # Low-stock alert
        print("\n[Alert] Low-stock products (< 10):")
        low_stock = conn.execute(text("SELECT name, stock FROM products WHERE stock < 10")).fetchall()
        for name, stock in low_stock:
            print(f"{name:<10}: only {stock} left")

        # Stretch 2: Revenue per product
        print("\n[Report] Revenue per product:")
        revenues = conn.execute(text("""
            SELECT p.name, SUM(p.price * o.quantity) as total_revenue
            FROM products AS p
            LEFT JOIN orders AS o ON o.product_id = p.id 
            GROUP BY p.name""")).fetchall()
    
        for name, rev in revenues:
            print(f"{name:<10} ${rev or 0:.2f}")

        # Stretch 3: Never-ordered users
        print("\n[Report] Users with no orders:")
        no_orders = conn.execute(text("""
            SELECT u.email
            FROM users AS u
            LEFT JOIN orders AS o ON o.user_id = u.id
            WHERE o.id IS NULL"""))

        for email, in no_orders:
            print(f"{email}")
        print("=======================\n")

def add_product(engine, name, category, price, stock):
    """INSERT a product and return its new id."""
    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO products (name, category, price, stock)
            VALUES(:name, :category, :price, :stock)
            RETURNING id"""), {
                "name": name, 
                "category": category, 
                "price": price, 
                "stock": stock
            })

        return result.scalar()

def place_order(engine, email, product_name, quantity):
    """Create an order and decrement stock in one transaction."""
    with engine.begin() as conn:   # begin() commits on success, rolls back on error
        # 1. Look up user_id by email
        user_id = conn.execute(text("SELECT id FROM users WHERE email = :email"), 
                               {"email": email}).scalar()
        if not user_id:
            raise ValueError(f"User with email: '{email}' not found.")

        # 2. Look up product id and stock by name
        product = conn.execute(text("SELECT id, stock FROM products WHERE name = :name"),
                                     {"name": product_name}).fetchone()
        if not product:
            raise ValueError(f"Product: '{product_name}' not found.")
        
        product_id, current_stock = product

        # 3. Refuse the order if stock would go negative
        if current_stock < quantity:
            raise ValueError(
                f"Insufficient stock for '{product_name}'.\n"
                f"Requested: {quantity}, Available: {current_stock}"
                )

        # 4. INSERT the order
        conn.execute(text("""
                INSERT INTO orders (user_id, product_id, quantity) 
                VALUES (:user_id, :product_id, :quantity)
                """), {
                    "user_id": user_id, 
                    "product_id": product_id, 
                    "quantity": quantity
                    })

        # 5. UPDATE the product's stock
        conn.execute(text("""
                UPDATE products 
                SET stock = stock - :quantity 
                WHERE id = :product_id
                """), {
                    "quantity": quantity, 
                    "product_id": product_id
                    })

def main():
    engine = get_engine()
    store_report(engine)

    while True:
        print("\nOptions: [1] Add Product  [2] Place Order  [q] Quit")
        choice = input("Select an option: ")

        if choice == '1':
            try:
                name = input("Name: ")
                category = input("Category: ")
                price = float(input("Price: "))
                stock = int(input("Stock: "))
                
                new_id = add_product(engine, name, category, price, stock)
                print(f"Success! '{name}' added with ID: {new_id}")
            except Exception as e:
                print(f"Error adding product: {e}")

        elif choice == '2':
            try:
                email = input("User Email: ")
                product_name = input("Product Name: ")
                quantity = int(input("Quantity: "))
                
                place_order(engine, email, product_name, quantity)
                print(f"Success! Order placed for {quantity}x '{product_name}'.")
            except Exception as e:
                print(f"Error placing order: {e}")

        elif choice == 'q':
            print("Exiting...")
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main()