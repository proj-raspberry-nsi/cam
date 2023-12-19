import sqlite3

class database:
    def __init__(self, dbPath:str):
        self.connection = sqlite3.connect(dbPath)
        self.cursor = self.connection.cursor()

    def getTables(self):
        sqlRes = self.connection.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        return list(map(lambda x: x[0], sqlRes))

    def getColumns(self, tableName):
        sqlRes = self.connection.execute(f'SELECT * FROM {tableName};')
        return list(map(lambda x: x[0], sqlRes.description))

    def createTable(self, tableName:str, columns:dict[str:str]):
        colNames = ', '.join(str(colName)+" "+type.upper() for colName, type in columns.items())
        sqlReq = f"CREATE TABLE {tableName} ({colNames});"
        self.cursor.execute(sqlReq)
        return sqlReq

    def insert(self, tableName:str, values:list):
        columns = self.getColumns(tableName)
        if len(columns) != len(values):
            raise IndexError("given values do not match with existing number of columns")
        columns = ', '.join(columns)
        values  = ', '.join('"'+str(val)+'"' for val in values)
        sqlReq = f"INSERT INTO {tableName} ({columns}) VALUES ({values});"
        self.cursor.execute(sqlReq)
        self.connection.commit()
        return sqlReq

    def getAll(self, tableName:str):
        sqlReq = f"SELECT * FROM {tableName};"
        sqlRes = self.connection.execute(sqlReq)
        return sqlRes.fetchall()

    def getRows(self, tableName:str, key:str, value:str):
        sqlReq = f"SELECT * FROM {tableName} WHERE {key}=='{value}';"
        sqlRes = self.connection.execute(sqlReq)
        return sqlRes.fetchall()

    def getCol(self, tableName:str, key:str):
        sqlReq = f"SELECT {key} FROM {tableName};"
        sqlRes = self.connection.execute(sqlReq)
        return list(map(lambda x: x[0], sqlRes.fetchall()))

    def delete(self, tableName:str, key:str, value:str):
        sqlReq = f"DELETE FROM {tableName} WHERE {key}=='{value}';"
        self.cursor.execute(sqlReq)
        self.connection.commit()
        return sqlReq

    def reset(self, tableName:str):
        sqlReq = f"DELETE FROM {tableName};"
        self.cursor.execute(sqlReq)
        self.connection.commit()
        return sqlReq

    def close(self):
        self.connection.close()