"""Django project package."""

# PyMySQL is a portable option for cPanel accounts where compiling mysqlclient
# is unavailable. It exposes the DB-API module expected by Django's MySQL
# backend and is harmless while the local SQLite backend is selected.
try:
    import pymysql
except ImportError:
    pymysql = None

if pymysql is not None:
    pymysql.install_as_MySQLdb()
