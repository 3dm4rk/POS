import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta
import csv

# ---------------------------- Database Setup ----------------------------
class Database:
    """Handles all database operations."""
    def __init__(self, db_name="store.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._populate_sample_data()

    def _create_tables(self):
        """Create products and sales tables if they don't exist."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                price REAL,
                FOREIGN KEY(sale_id) REFERENCES sales(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        ''')
        self.conn.commit()

    def _populate_sample_data(self):
        """Add sample products if the table is empty."""
        self.cursor.execute("SELECT COUNT(*) FROM products")
        if self.cursor.fetchone()[0] == 0:
            sample_products = [
                ("Apple", 0.50, 100),
                ("Banana", 0.30, 150),
                ("Bread", 1.20, 50),
                ("Milk", 1.50, 40),
                ("Eggs (dozen)", 2.00, 30),
            ]
            self.cursor.executemany(
                "INSERT INTO products (name, price, quantity) VALUES (?, ?, ?)",
                sample_products
            )
            self.conn.commit()

    def get_products(self):
        """Return all products as list of tuples (id, name, price, quantity)."""
        self.cursor.execute("SELECT id, name, price, quantity FROM products")
        return self.cursor.fetchall()

    def add_product(self, name, price, quantity):
        """Insert a new product."""
        self.cursor.execute(
            "INSERT INTO products (name, price, quantity) VALUES (?, ?, ?)",
            (name, price, quantity)
        )
        self.conn.commit()

    def update_product(self, product_id, name, price, quantity):
        """Update existing product."""
        self.cursor.execute(
            "UPDATE products SET name=?, price=?, quantity=? WHERE id=?",
            (name, price, quantity, product_id)
        )
        self.conn.commit()

    def delete_product(self, product_id):
        """Remove product from database."""
        self.cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
        self.conn.commit()

    def update_stock(self, product_id, new_quantity):
        """Set a product's quantity to new value."""
        self.cursor.execute(
            "UPDATE products SET quantity=? WHERE id=?",
            (new_quantity, product_id)
        )
        self.conn.commit()

    def record_sale(self, cart_items, total):
        """Record a sale and its items, then deduct stock."""
        # Insert sale header
        self.cursor.execute(
            "INSERT INTO sales (total) VALUES (?)",
            (total,)
        )
        sale_id = self.cursor.lastrowid

        # Insert sale items and update stock
        for item in cart_items:
            product_id, name, price, qty = item
            self.cursor.execute(
                "INSERT INTO sale_items (sale_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (sale_id, product_id, qty, price)
            )
            # Deduct stock
            self.cursor.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                (qty, product_id)
            )
        self.conn.commit()

    def get_all_sales(self):
        """Return all sales as list of (id, total, timestamp)."""
        self.cursor.execute("SELECT id, total, timestamp FROM sales ORDER BY timestamp DESC")
        return self.cursor.fetchall()

    def get_sale_items(self, sale_id):
        """Return items for a given sale as list of (product_name, quantity, price, subtotal)."""
        self.cursor.execute('''
            SELECT p.name, si.quantity, si.price, (si.quantity * si.price) as subtotal
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = ?
        ''', (sale_id,))
        return self.cursor.fetchall()

    # ---------------------- Report Methods ----------------------
    def get_sales_summary_by_date_range(self, start_date, end_date):
        """Return total sales, number of transactions, and average sale value for a date range."""
        self.cursor.execute('''
            SELECT 
                COALESCE(SUM(total), 0) as total_sales,
                COUNT(*) as num_transactions,
                COALESCE(AVG(total), 0) as avg_sale
            FROM sales
            WHERE date(timestamp) BETWEEN ? AND ?
        ''', (start_date, end_date))
        return self.cursor.fetchone()

    def get_daily_sales(self, start_date, end_date):
        """Return daily totals for the given date range."""
        self.cursor.execute('''
            SELECT date(timestamp) as day, SUM(total) as daily_total
            FROM sales
            WHERE date(timestamp) BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day
        ''', (start_date, end_date))
        return self.cursor.fetchall()

    def get_top_products(self, limit=10):
        """Return top selling products by quantity sold."""
        self.cursor.execute('''
            SELECT p.name, SUM(si.quantity) as total_sold, SUM(si.quantity * si.price) as revenue
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            GROUP BY si.product_id
            ORDER BY total_sold DESC
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()

    def get_low_stock_products(self, threshold=10):
        """Return products with quantity <= threshold."""
        self.cursor.execute("SELECT id, name, quantity FROM products WHERE quantity <= ?", (threshold,))
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()


# ---------------------------- Product Manager ----------------------------
class ProductManager:
    """Window for managing products (add, edit, delete)."""
    def __init__(self, parent, db, refresh_callback):
        self.db = db
        self.refresh_callback = refresh_callback

        self.window = tk.Toplevel(parent)
        self.window.title("Product Manager")
        self.window.geometry("600x400")
        self.window.grab_set()  # modal

        # Treeview to display products
        columns = ("ID", "Name", "Price", "Quantity")
        self.tree = ttk.Treeview(self.window, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Buttons
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Add", command=self.add_product).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit", command=self.edit_product).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete", command=self.delete_product).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.refresh_product_list()

    def refresh_product_list(self):
        """Load products from DB into the treeview."""
        for row in self.tree.get_children():
            self.tree.delete(row)
        for product in self.db.get_products():
            self.tree.insert("", tk.END, values=product)

    def add_product(self):
        """Open a dialog to add a new product."""
        name = simpledialog.askstring("Add Product", "Product name:", parent=self.window)
        if not name:
            return
        price = simpledialog.askfloat("Add Product", "Price:", parent=self.window)
        if price is None:
            return
        qty = simpledialog.askinteger("Add Product", "Initial quantity:", parent=self.window)
        if qty is None:
            return
        self.db.add_product(name, price, qty)
        self.refresh_product_list()
        self.refresh_callback()  # refresh main product list

    def edit_product(self):
        """Edit selected product."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Please select a product to edit.")
            return
        values = self.tree.item(selected[0], "values")
        product_id, name, price, qty = values

        new_name = simpledialog.askstring("Edit Product", "New name:", initialvalue=name, parent=self.window)
        if not new_name:
            return
        new_price = simpledialog.askfloat("Edit Product", "New price:", initialvalue=price, parent=self.window)
        if new_price is None:
            return
        new_qty = simpledialog.askinteger("Edit Product", "New quantity:", initialvalue=qty, parent=self.window)
        if new_qty is None:
            return

        self.db.update_product(product_id, new_name, new_price, new_qty)
        self.refresh_product_list()
        self.refresh_callback()

    def delete_product(self):
        """Delete selected product."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Please select a product to delete.")
            return
        if messagebox.askyesno("Confirm Delete", "Delete selected product?"):
            product_id = self.tree.item(selected[0], "values")[0]
            self.db.delete_product(product_id)
            self.refresh_product_list()
            self.refresh_callback()


# ---------------------------- Transaction Viewer ----------------------------
class TransactionViewer:
    """Window to view all past sales and details."""
    def __init__(self, parent, db):
        self.db = db
        self.window = tk.Toplevel(parent)
        self.window.title("Transaction History")
        self.window.geometry("800x500")
        self.window.grab_set()

        # Main frame with left (sales list) and right (details)
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left frame: list of sales
        left_frame = ttk.LabelFrame(main_frame, text="Sales", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        columns = ("ID", "Date", "Total")
        self.sales_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=20)
        for col in columns:
            self.sales_tree.heading(col, text=col)
            self.sales_tree.column(col, width=120)
        self.sales_tree.pack(fill=tk.BOTH, expand=True)
        self.sales_tree.bind("<<TreeviewSelect>>", self.on_sale_selected)

        # Right frame: sale details
        right_frame = ttk.LabelFrame(main_frame, text="Sale Details", padding=5)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        detail_columns = ("Product", "Quantity", "Price", "Subtotal")
        self.detail_tree = ttk.Treeview(right_frame, columns=detail_columns, show="headings", height=20)
        for col in detail_columns:
            self.detail_tree.heading(col, text=col)
            self.detail_tree.column(col, width=120)
        self.detail_tree.pack(fill=tk.BOTH, expand=True)

        # Populate sales list
        self.refresh_sales_list()

    def refresh_sales_list(self):
        """Load all sales from DB into the left tree."""
        for row in self.sales_tree.get_children():
            self.sales_tree.delete(row)
        for sale in self.db.get_all_sales():
            # sale: (id, total, timestamp)
            # Format timestamp nicely
            try:
                dt = datetime.strptime(sale[2], "%Y-%m-%d %H:%M:%S")
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = sale[2]
            self.sales_tree.insert("", tk.END, values=(sale[0], date_str, f"${sale[1]:.2f}"))

    def on_sale_selected(self, event):
        """When a sale is selected, show its items."""
        selected = self.sales_tree.selection()
        if not selected:
            return
        sale_id = self.sales_tree.item(selected[0], "values")[0]
        items = self.db.get_sale_items(sale_id)

        # Clear detail tree
        for row in self.detail_tree.get_children():
            self.detail_tree.delete(row)

        # Populate with items
        for item in items:
            name, qty, price, subtotal = item
            self.detail_tree.insert("", tk.END, values=(name, qty, f"${price:.2f}", f"${subtotal:.2f}"))


# ---------------------------- Report Viewer ----------------------------
class ReportViewer:
    """Window to view sales reports and analytics."""
    def __init__(self, parent, db):
        self.db = db
        self.window = tk.Toplevel(parent)
        self.window.title("Sales Reports & Analytics")
        self.window.geometry("900x600")
        self.window.grab_set()

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create tabs
        self.summary_tab = ttk.Frame(self.notebook)
        self.top_products_tab = ttk.Frame(self.notebook)
        self.low_stock_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.summary_tab, text="Sales Summary")
        self.notebook.add(self.top_products_tab, text="Top Selling Products")
        self.notebook.add(self.low_stock_tab, text="Low Stock Alerts")

        self._build_summary_tab()
        self._build_top_products_tab()
        self._build_low_stock_tab()

        # Button to export current tab data to CSV
        export_btn = ttk.Button(self.window, text="Export Current Report to CSV", command=self.export_current_report)
        export_btn.pack(pady=5)

    def _build_summary_tab(self):
        """Build the Sales Summary tab."""
        # Date range selection
        range_frame = ttk.LabelFrame(self.summary_tab, text="Date Range", padding=5)
        range_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(range_frame, text="From:").grid(row=0, column=0, padx=5, pady=5)
        self.start_date_entry = ttk.Entry(range_frame, width=12)
        self.start_date_entry.grid(row=0, column=1, padx=5, pady=5)
        self.start_date_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))

        ttk.Label(range_frame, text="To:").grid(row=0, column=2, padx=5, pady=5)
        self.end_date_entry = ttk.Entry(range_frame, width=12)
        self.end_date_entry.grid(row=0, column=3, padx=5, pady=5)
        self.end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        # Predefined range buttons
        btn_frame = ttk.Frame(range_frame)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=5)

        ttk.Button(btn_frame, text="Today", command=self.set_today).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="This Week", command=self.set_this_week).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="This Month", command=self.set_this_month).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Last Month", command=self.set_last_month).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="All Time", command=self.set_all_time).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_summary).pack(side=tk.LEFT, padx=2)

        # Summary display area
        summary_frame = ttk.LabelFrame(self.summary_tab, text="Summary", padding=5)
        summary_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.summary_text = tk.Text(summary_frame, height=6, width=50, state="normal")
        self.summary_text.pack(fill=tk.BOTH, expand=True)

        # Daily breakdown tree
        daily_frame = ttk.LabelFrame(self.summary_tab, text="Daily Breakdown", padding=5)
        daily_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        daily_cols = ("Date", "Total Sales")
        self.daily_tree = ttk.Treeview(daily_frame, columns=daily_cols, show="headings", height=10)
        for col in daily_cols:
            self.daily_tree.heading(col, text=col)
            self.daily_tree.column(col, width=150)
        self.daily_tree.pack(fill=tk.BOTH, expand=True)

        self.refresh_summary()

    def _build_top_products_tab(self):
        """Build the Top Selling Products tab."""
        # Limit selection
        limit_frame = ttk.Frame(self.top_products_tab)
        limit_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(limit_frame, text="Show top:").pack(side=tk.LEFT)
        self.top_limit = ttk.Spinbox(limit_frame, from_=1, to=50, width=5)
        self.top_limit.pack(side=tk.LEFT, padx=5)
        self.top_limit.set(10)
        ttk.Button(limit_frame, text="Refresh", command=self.refresh_top_products).pack(side=tk.LEFT, padx=5)

        # Treeview for top products
        top_frame = ttk.Frame(self.top_products_tab)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cols = ("Product", "Quantity Sold", "Revenue")
        self.top_tree = ttk.Treeview(top_frame, columns=cols, show="headings", height=20)
        for col in cols:
            self.top_tree.heading(col, text=col)
            self.top_tree.column(col, width=200)
        self.top_tree.pack(fill=tk.BOTH, expand=True)

        self.refresh_top_products()

    def _build_low_stock_tab(self):
        """Build the Low Stock Alerts tab."""
        # Threshold selection
        thresh_frame = ttk.Frame(self.low_stock_tab)
        thresh_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(thresh_frame, text="Alert when stock ≤:").pack(side=tk.LEFT)
        self.threshold = ttk.Spinbox(thresh_frame, from_=0, to=100, width=5)
        self.threshold.pack(side=tk.LEFT, padx=5)
        self.threshold.set(10)
        ttk.Button(thresh_frame, text="Refresh", command=self.refresh_low_stock).pack(side=tk.LEFT, padx=5)

        # Treeview for low stock products
        stock_frame = ttk.Frame(self.low_stock_tab)
        stock_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cols = ("ID", "Product", "Current Stock")
        self.stock_tree = ttk.Treeview(stock_frame, columns=cols, show="headings", height=20)
        for col in cols:
            self.stock_tree.heading(col, text=col)
            self.stock_tree.column(col, width=150)
        self.stock_tree.pack(fill=tk.BOTH, expand=True)

        self.refresh_low_stock()

    # -------------------- Date helpers --------------------
    def set_today(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, today)
        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, today)
        self.refresh_summary()

    def set_this_week(self):
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, start.strftime("%Y-%m-%d"))
        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, today.strftime("%Y-%m-%d"))
        self.refresh_summary()

    def set_this_month(self):
        today = datetime.now()
        start = today.replace(day=1)
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, start.strftime("%Y-%m-%d"))
        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, today.strftime("%Y-%m-%d"))
        self.refresh_summary()

    def set_last_month(self):
        today = datetime.now()
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, first_day_last_month.strftime("%Y-%m-%d"))
        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, last_day_last_month.strftime("%Y-%m-%d"))
        self.refresh_summary()

    def set_all_time(self):
        # Set a very early date
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, "2000-01-01")
        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.refresh_summary()

    def refresh_summary(self):
        """Fetch and display sales summary for selected date range."""
        start = self.start_date_entry.get()
        end = self.end_date_entry.get()
        try:
            total_sales, num_trans, avg_sale = self.db.get_sales_summary_by_date_range(start, end)
            self.summary_text.delete(1.0, tk.END)
            self.summary_text.insert(tk.END, f"Date Range: {start} to {end}\n")
            self.summary_text.insert(tk.END, f"Total Sales: ${total_sales:.2f}\n")
            self.summary_text.insert(tk.END, f"Number of Transactions: {num_trans}\n")
            self.summary_text.insert(tk.END, f"Average Sale: ${avg_sale:.2f}\n")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load summary: {e}")

        # Daily breakdown
        for row in self.daily_tree.get_children():
            self.daily_tree.delete(row)
        try:
            daily_data = self.db.get_daily_sales(start, end)
            for day, total in daily_data:
                self.daily_tree.insert("", tk.END, values=(day, f"${total:.2f}"))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load daily breakdown: {e}")

    def refresh_top_products(self):
        """Fetch and display top selling products."""
        try:
            limit = int(self.top_limit.get())
            data = self.db.get_top_products(limit)
            for row in self.top_tree.get_children():
                self.top_tree.delete(row)
            for name, qty, revenue in data:
                self.top_tree.insert("", tk.END, values=(name, qty, f"${revenue:.2f}"))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load top products: {e}")

    def refresh_low_stock(self):
        """Fetch and display low stock products."""
        try:
            threshold = int(self.threshold.get())
            data = self.db.get_low_stock_products(threshold)
            for row in self.stock_tree.get_children():
                self.stock_tree.delete(row)
            for pid, name, qty in data:
                self.stock_tree.insert("", tk.END, values=(pid, name, qty))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load low stock: {e}")

    def export_current_report(self):
        """Export data from the currently selected tab to a CSV file."""
        current_tab = self.notebook.index(self.notebook.select())
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not filename:
            return

        try:
            if current_tab == 0:  # Sales Summary
                # Export daily breakdown
                data = []
                for child in self.daily_tree.get_children():
                    values = self.daily_tree.item(child, "values")
                    data.append(values)
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Date", "Total Sales"])
                    writer.writerows(data)
            elif current_tab == 1:  # Top Products
                data = []
                for child in self.top_tree.get_children():
                    values = self.top_tree.item(child, "values")
                    data.append(values)
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Product", "Quantity Sold", "Revenue"])
                    writer.writerows(data)
            elif current_tab == 2:  # Low Stock
                data = []
                for child in self.stock_tree.get_children():
                    values = self.stock_tree.item(child, "values")
                    data.append(values)
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Product", "Current Stock"])
                    writer.writerows(data)
            messagebox.showinfo("Export Successful", f"Report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Error exporting data: {e}")


# ---------------------------- Main POS Application ----------------------------
class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Store POS System")
        self.root.geometry("900x600")

        self.db = Database()

        # Cart data: list of (product_id, name, price, quantity)
        self.cart = []
        self.total_price = 0.0

        self._setup_ui()
        self.refresh_product_list()

    def _setup_ui(self):
        """Create the main layout."""
        # Left frame: product list
        left_frame = ttk.LabelFrame(self.root, text="Products", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Product list (Treeview)
        columns = ("ID", "Name", "Price", "Stock")
        self.product_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=20)
        for col in columns:
            self.product_tree.heading(col, text=col)
            self.product_tree.column(col, width=100)
        self.product_tree.pack(fill=tk.BOTH, expand=True)

        # Add to cart controls
        add_frame = ttk.Frame(left_frame)
        add_frame.pack(fill=tk.X, pady=5)

        ttk.Label(add_frame, text="Quantity:").pack(side=tk.LEFT)
        self.qty_entry = ttk.Entry(add_frame, width=10)
        self.qty_entry.pack(side=tk.LEFT, padx=5)
        self.qty_entry.insert(0, "1")

        ttk.Button(add_frame, text="Add to Cart", command=self.add_to_cart).pack(side=tk.LEFT, padx=5)

        # Right frame: cart
        right_frame = ttk.LabelFrame(self.root, text="Shopping Cart", padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Cart list (Treeview)
        cart_cols = ("ID", "Name", "Price", "Qty", "Subtotal")
        self.cart_tree = ttk.Treeview(right_frame, columns=cart_cols, show="headings", height=15)
        for col in cart_cols:
            self.cart_tree.heading(col, text=col)
            self.cart_tree.column(col, width=100)
        self.cart_tree.pack(fill=tk.BOTH, expand=True)

        # Cart control buttons
        cart_btn_frame = ttk.Frame(right_frame)
        cart_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(cart_btn_frame, text="Remove Selected", command=self.remove_from_cart).pack(side=tk.LEFT, padx=5)
        ttk.Button(cart_btn_frame, text="Clear Cart", command=self.clear_cart).pack(side=tk.LEFT, padx=5)

        # Total and checkout
        total_frame = ttk.Frame(right_frame)
        total_frame.pack(fill=tk.X, pady=10)

        self.total_label = ttk.Label(total_frame, text="Total: $0.00", font=("Arial", 14, "bold"))
        self.total_label.pack(side=tk.LEFT)

        ttk.Button(total_frame, text="Process Sale", command=self.process_sale).pack(side=tk.RIGHT, padx=5)

        # Bottom buttons: Manage Products, View Transactions, Reports
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        ttk.Button(bottom_frame, text="Manage Products", command=self.open_product_manager).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="View Transactions", command=self.open_transaction_viewer).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="Reports", command=self.open_report_viewer).pack(side=tk.LEFT, padx=5)

    def refresh_product_list(self):
        """Update the product treeview with current data from DB."""
        for row in self.product_tree.get_children():
            self.product_tree.delete(row)
        for product in self.db.get_products():
            self.product_tree.insert("", tk.END, values=product)

    def add_to_cart(self):
        """Add selected product to cart with given quantity."""
        selected = self.product_tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Please select a product.")
            return

        try:
            qty = int(self.qty_entry.get())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid quantity", "Quantity must be a positive integer.")
            return

        product_values = self.product_tree.item(selected[0], "values")
        product_id = int(product_values[0])
        name = product_values[1]
        price = float(product_values[2])
        stock = int(product_values[3])

        if qty > stock:
            messagebox.showerror("Insufficient stock", f"Only {stock} available.")
            return

        # Check if product already in cart
        for i, item in enumerate(self.cart):
            if item[0] == product_id:
                new_qty = item[3] + qty
                if new_qty > stock:
                    messagebox.showerror("Insufficient stock", f"Cannot add {qty}, only {stock - item[3]} left.")
                    return
                self.cart[i] = (product_id, name, price, new_qty)
                break
        else:
            self.cart.append((product_id, name, price, qty))

        self.update_cart_display()
        self.update_total()

    def update_cart_display(self):
        """Refresh the cart treeview."""
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        for item in self.cart:
            product_id, name, price, qty = item
            subtotal = price * qty
            self.cart_tree.insert("", tk.END, values=(product_id, name, f"${price:.2f}", qty, f"${subtotal:.2f}"))

    def update_total(self):
        """Calculate and display total."""
        total = sum(item[2] * item[3] for item in self.cart)
        self.total_price = total
        self.total_label.config(text=f"Total: ${total:.2f}")

    def remove_from_cart(self):
        """Remove selected cart item."""
        selected = self.cart_tree.selection()
        if not selected:
            return
        index = self.cart_tree.index(selected[0])
        del self.cart[index]
        self.update_cart_display()
        self.update_total()

    def clear_cart(self):
        """Empty the cart."""
        self.cart.clear()
        self.update_cart_display()
        self.update_total()

    def process_sale(self):
        """Record the sale, deduct stock, and clear cart."""
        if not self.cart:
            messagebox.showwarning("Empty cart", "No items to sell.")
            return

        # Double‑check stock again before finalizing
        for item in self.cart:
            product_id, name, price, qty = item
            self.db.cursor.execute("SELECT quantity FROM products WHERE id=?", (product_id,))
            current_stock = self.db.cursor.fetchone()[0]
            if qty > current_stock:
                messagebox.showerror("Stock changed", f"{name} now only has {current_stock} in stock. Please update cart.")
                return

        # Record sale
        self.db.record_sale(self.cart, self.total_price)

        # Store total before clearing (FIX: save total before it's reset)
        sale_total = self.total_price

        # Update product list and clear cart
        self.refresh_product_list()
        self.clear_cart()
        messagebox.showinfo("Success", f"Sale completed! Total: ${sale_total:.2f}")

    def open_product_manager(self):
        """Open product management window."""
        ProductManager(self.root, self.db, self.refresh_product_list)

    def open_transaction_viewer(self):
        """Open transaction history window."""
        TransactionViewer(self.root, self.db)

    def open_report_viewer(self):
        """Open reports and analytics window."""
        ReportViewer(self.root, self.db)


# ---------------------------- Run the Application ----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()