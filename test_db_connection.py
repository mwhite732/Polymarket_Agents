"""Test PostgreSQL connection with detailed diagnostics."""
import sys
from urllib.parse import quote_plus
import psycopg2
from sqlalchemy import create_engine, text

def test_connection():
    print("=" * 60)
    print("PostgreSQL Connection Diagnostics")
    print("=" * 60)

    # Test 1: Load .env file
    print("\n1. Loading .env file...")
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        db_url = os.getenv('DATABASE_URL')
        print(f"   ✓ DATABASE_URL loaded: {db_url[:30]}...")
    except Exception as e:
        print(f"   ✗ Error loading .env: {e}")
        return

    # Test 2: Parse connection string
    print("\n2. Parsing connection string...")
    try:
        # Extract components
        if db_url.startswith('postgresql://'):
            parts = db_url.replace('postgresql://', '').split('@')
            user_pass = parts[0].split(':')
            host_db = parts[1].split('/')

            username = user_pass[0]
            password = user_pass[1] if len(user_pass) > 1 else ''
            host_port = host_db[0].split(':')
            host = host_port[0]
            port = host_port[1] if len(host_port) > 1 else '5432'
            database = host_db[1].split('?')[0] if len(host_db) > 1 else ''

            print(f"   Username: {username}")
            print(f"   Password: {'*' * len(password)} (length: {len(password)})")
            print(f"   Host: {host}")
            print(f"   Port: {port}")
            print(f"   Database: {database}")
    except Exception as e:
        print(f"   ✗ Error parsing URL: {e}")
        return

    # Test 3: Try psycopg2 directly
    print("\n3. Testing with psycopg2 (raw connection)...")
    try:
        conn = psycopg2.connect(
            dbname=database,
            user=username,
            password=password,  # Will be decoded from URL encoding
            host=host,
            port=port
        )
        print("   ✓ psycopg2 connection successful!")
        conn.close()
    except psycopg2.OperationalError as e:
        print(f"   ✗ psycopg2 connection failed:")
        print(f"   Error: {e}")

        # Check specific error types
        error_str = str(e)
        if "password authentication failed" in error_str:
            print("\n   DIAGNOSIS: Password is incorrect or not accepted")
            print("   Solutions:")
            print("   1. Verify password in pgAdmin (try connecting there)")
            print("   2. Check if special characters are properly encoded")
            print("   3. Try resetting postgres user password:")
            print("      ALTER USER postgres WITH PASSWORD 'newpassword';")
        elif "database" in error_str and "does not exist" in error_str:
            print("\n   DIAGNOSIS: Database doesn't exist")
            print("   Solution: Create database in pgAdmin or run:")
            print("   createdb polymarket_gaps")
        elif "Connection refused" in error_str or "could not connect" in error_str:
            print("\n   DIAGNOSIS: PostgreSQL server not running or wrong host/port")
            print("   Solutions:")
            print("   1. Start PostgreSQL service")
            print("   2. Try host='127.0.0.1' instead of 'localhost'")

        print("\n4. Alternative connection strings to try:")
        print(f"   Option A: postgresql://{username}:{quote_plus(password)}@127.0.0.1:{port}/{database}")
        print(f"   Option B: postgresql://{username}:{quote_plus(password)}@localhost:{port}/{database}")
        return
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        return

    # Test 4: Try SQLAlchemy
    print("\n4. Testing with SQLAlchemy...")
    try:
        engine = create_engine(db_url, echo=False)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"   ✓ SQLAlchemy connection successful!")
            print(f"   PostgreSQL version: {version[:50]}...")
    except Exception as e:
        print(f"   ✗ SQLAlchemy connection failed: {e}")
        return

    # Test 5: Check database tables
    print("\n5. Checking database schema...")
    try:
        engine = create_engine(db_url, echo=False)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            if tables:
                print(f"   ✓ Found {len(tables)} tables: {', '.join(tables)}")
            else:
                print("   ⚠ No tables found. Run migrations/init_db.sql")
    except Exception as e:
        print(f"   ✗ Error checking schema: {e}")

    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED! Database connection is working.")
    print("=" * 60)

if __name__ == '__main__':
    test_connection()
