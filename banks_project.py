# Code for ETL operations on bank market capitalization data

import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import numpy as np
import sqlite3


def log_progress(message):
    timestamp_format = '%Y-%b-%d-%H:%M:%S'
    now = datetime.now()
    timestamp = now.strftime(timestamp_format)
    with open('code_log.txt', 'a') as f:
        f.write(timestamp + ',' + message + '\n')


def extract(url, table_attribs):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    heading = soup.find(id='By_market_capitalization')
    table = heading.find_next('table')
    data = []

    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) >= 3:
            name = cells[1].get_text(strip=True)
            market_cap = cells[2].get_text()

            if market_cap.endswith('\n'):
                market_cap = market_cap[:-1]

            market_cap = float(market_cap.strip())
            data.append([name, market_cap])

    df = pd.DataFrame(data, columns=table_attribs)
    df.rename(
        columns={'Market cap (US$ billion)': 'MC_USD_Billion'},
        inplace=True
    )
    return df


def transform(df, csv_path):
    exchange_rate_df = pd.read_csv(csv_path)
    exchange_rate = exchange_rate_df.set_index('Currency').to_dict()['Rate']

    gbp_rate = float(exchange_rate['GBP'])
    eur_rate = float(exchange_rate['EUR'])
    inr_rate = float(exchange_rate['INR'])

    df['MC_GBP_Billion'] = [
        np.round(x * gbp_rate, 2) for x in df['MC_USD_Billion']
    ]
    df['MC_EUR_Billion'] = [
        np.round(x * eur_rate, 2) for x in df['MC_USD_Billion']
    ]
    df['MC_INR_Billion'] = [
        np.round(x * inr_rate, 2) for x in df['MC_USD_Billion']
    ]
    return df


def load_to_csv(df, output_path):
    df.to_csv(output_path, index=False)


def load_to_db(df, sql_connection, table_name):
    df.to_sql(
        table_name,
        sql_connection,
        if_exists='replace',
        index=False
    )


def run_queries(query_statement, sql_connection):
    print('\nQuery:', query_statement)
    query_output = pd.read_sql_query(query_statement, sql_connection)
    print(query_output.to_string(index=False))


url = (
    'https://web.archive.org/web/20230908091635/'
    'https://en.wikipedia.org/wiki/List_of_largest_banks'
)
table_attribs = ['Name', 'Market cap (US$ billion)']
output_path = '/home/project/Largest_banks_data.csv'

log_progress('Extraction started')
df = extract(url, table_attribs)
# print(df)
log_progress('Data extraction complete')

df = transform(df, 'exchange_rate.csv')
# print(df.to_string(index=False))
# print(df['MC_EUR_Billion'][4])
log_progress('Data transformation complete')

load_to_csv(df, output_path)
log_progress('Data saved to CSV file')

sql_connection = sqlite3.connect('/home/project/Banks.db')
log_progress('Database connection initiated')

try:
    load_to_db(df, sql_connection, 'Largest_banks')
    log_progress('Data loaded to database as Largest_banks table')

    run_queries('SELECT * FROM Largest_banks', sql_connection)

    run_queries(
        'SELECT AVG(MC_GBP_Billion) FROM Largest_banks',
        sql_connection
    )

    run_queries(
        'SELECT Name FROM Largest_banks LIMIT 5',
        sql_connection
    )

    log_progress('Database queries completed')
finally:
    sql_connection.close()
    log_progress('Database connection closed')