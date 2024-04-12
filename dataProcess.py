import pandas as pd
import torch
import math
from torch.nn.utils.rnn import pad_sequence
from datetime import datetime, timedelta
from torch.utils.data import Dataset, DataLoader


def dataToTensorHourly(path, separateByDay=True, missingThreshold=0.1, columnToDelete=['wind_dir', 'unixtime'], start=None, end=(datetime.now().date())):
    """
    Takes the relative path to an hourly weather csv file and returns a tensor

    :param str path: The relative path of the hourly weather csv to be parsed
    :param bool separateByDay: Whether or not to output multiple tensors for each day
    :param float missingThreshold: Removes columns with a missing data ratio greather than this value
    :param list columnToDelete: Names of columns to remove
    :param datetime.date start: Only count data from this date
    :param datetime.date end: Only count data before this date
    """
    df = pd.read_csv(path)
    df = df.rename(columns={'date_time_local':'hour'})
    df['day'] = None
    df['day_since_beginning'] = None
    if start is None:
        start = datetime.strptime(df.iloc[-1]['hour'], '%Y-%m-%d %H:%M:%S EST')
        start = start.date()
    for index, row in df.iterrows():
        if pd.isna(df.at[index, 'pressure_station']):
            df = df.drop(index)
        else:
            try:
                date = datetime.strptime(row['hour'], '%Y-%m-%d %H:%M:%S EDT')
            except:
                date = datetime.strptime(row['hour'], '%Y-%m-%d %H:%M:%S EST')
            if date.date() > end or date.date() < start:
                df = df.drop(index)
            else:
                df.at[index, 'day_since_beginning'] = int((date.date() - start).days)
                df.at[index,'hour'] = int(date.hour)
                df.at[index,'day'] = int((date - datetime.strptime(str(date.year), "%Y")).days)
    if columnToDelete is not None:
        df = df.drop(labels=columnToDelete, axis=1)
    for i in list(df.columns.values):
        if df[i].isna().sum() / df.shape[0] > missingThreshold:
            df = df.drop(labels=i, axis=1)
    if missingThreshold > 0:
        df.interpolate()
    # print(df)
    if separateByDay:
        tensors = []
        group = df.groupby('day_since_beginning')
        for _, c in group:
            # print(_)
            c = c.drop(labels='day_since_beginning', axis=1)
            tensors.insert(0, torch.tensor(c.to_numpy().astype(float)))
        return tensors
    df = df.drop(labels='day_since_beginning', axis=1)
    return [torch.tensor(df.to_numpy().astype(float))]

def dailyTargets(path, target='avg_temperature', start=None, end=datetime.now().date()):
    df = pd.read_csv(path)
    if start is None:
        start = datetime.strptime(df.iloc[-1]['date'], '%Y-%m-%d')
        start = start.date()
    for index, row in df.iterrows():
        date = datetime.strptime(row['date'], "%Y-%m-%d").date()
        if date > end or date < start:
            df = df.drop(index)
    return(torch.tensor(df[target].to_numpy().astype(float)))

class dataSet(Dataset):
    def __init__(self, hourly_path, daily_path, start, end):
        data_end = (datetime.combine(end, datetime.min.time()) - timedelta(1)).date()
        target_start = (datetime.combine(start, datetime.min.time()) + timedelta(1)).date()
        self.data = dataToTensorHourly(hourly_path, start=start, end=data_end)
        self.targets = dailyTargets(daily_path, start=target_start, end=end)
        
    def __len__(self):
        return self.targets.shape[0]
    
    def __getitem__(self, idx):
        return self.data[idx], self.targets[idx]
    
def generateData(hourly_path, daily_path, start, end, batch_size=1, shuffle=False) -> dict:
    """
    Generates dataloaders based on given data

    :param str hourly_path: The path to an hourly data csv file
    :param str daily_path: The path to an daily data csv file
    :param datetime.date start: The first day to collect data from
    :param datetime.date end: The last day to collect data from
    :param int batch_size: The batch size of the training data
    :param bool shuffle: Whether or not to shuffle the data within the 3 datasets (doesnt shuffle between train, val, and test)
    """
    data = dataSet(hourly_path, daily_path, start, end)
    # We train on older data as we cant 'train on the future'
    train = data[math.floor(len(data) * .4) + 1:]
    # Therefore we validate on the newer data
    validation = data[math.floor(len(data) * .2) + 1 : math.floor(len(data) * .4)]
    test = data[:math.floor(len(data) * .2)]
    return{"train": DataLoader(train, batch_size=batch_size, shuffle=shuffle), "validation" : DataLoader(validation, shuffle=shuffle), "test" : DataLoader(test, shuffle=shuffle)}

if __name__ == "__main__":
    # Example of how to generate dataloaders
    # Recommended dates for datasets:
    # 100_day: start=(2024, 1, 3) | end=(2024, 4, 10)
    # three_year: start=(2021, 4, 13) | end=(2024, 4, 10)
    # ten_year: start=(2014, 4, 16) | end=(2024, 4, 10)

    start = datetime(2014, 4, 16).date()
    end = datetime(2024, 4, 10).date()
    hourly_path ='.\\Raw data\\ten_year\\weatherstats_toronto_hourly.csv'
    daily_path =  '.\\Raw data\\ten_year\\weatherstats_toronto_daily.csv'

    loaders = generateData(hourly_path, daily_path, start, end, 10, False)
    print(loaders)

