# utils/csv_writer.py

import csv

def write_data_to_csv(data_list, headers, region):
    """
    Writes data to a CSV file with dynamic columns.

    :param data_list: List of dictionaries containing data for each customer
    :param headers: List of column names in the desired order
    :param region: Region name
    :return: Filename of the written CSV file
    """
    filename = f"{region.lower()}_customers_data.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore')
        csv_writer.writeheader()
        for data in data_list:
            csv_writer.writerow(data)
    return filename
