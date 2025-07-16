def build_sqlalchemy_uri(db_record) -> str:
    return f"{db_record.db_type}://{db_record.username}:{db_record.password}@{db_record.host}:{db_record.port}/{db_record.database}"
