from database import recreate_tables

if __name__ == "__main__":
    try:
        print("Starting database update...")
        recreate_tables()
        print("Database update completed successfully!")
    except Exception as e:
        print(f"Error updating database: {str(e)}") 