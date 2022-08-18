# -*- coding: utf-8 -*-
# !/usr/bin/python3

# python3 -m pip install yagmail psutil --no-cache-dir
import datetime
import json
import os
import traceback
from operator import getitem

import yagmail
import psutil
import requests
from collections import OrderedDict


def get911(key):
    with open('/home/pi/.911') as f:
        data = json.load(f)
    return data[key]


EMAIL_USER = get911('EMAIL_USER')
EMAIL_APPPW = get911('EMAIL_APPPW')
EMAIL_RECEIVER = get911('EMAIL_RECEIVER')


def getLog():
    try:
        with open(LOG_FILE) as inFile:
            data = json.load(inFile)
    except Exception as ex:
        data = {}
    return data


def getMatches():
    # Set matches
    matches = {}

    # Get Leagues JSON
    yesterday = datetime.datetime.strftime(datetime.datetime.now() - datetime.timedelta(1), "%Y-%m-%d")
    yesterdayJSON = json.loads(requests.get("https://sportscentral.io/new-api/matches?date=" + yesterday).content)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    todayJSON = json.loads(requests.get("https://sportscentral.io/new-api/matches?date=" + today).content)
    tomorrow = datetime.datetime.strftime(datetime.datetime.now() + datetime.timedelta(1), "%Y-%m-%d")
    tomorrowJSON = json.loads(requests.get("https://sportscentral.io/new-api/matches?date=" + tomorrow).content)
    allJSON = {"yesterday": yesterdayJSON, "today": todayJSON, "tomorrow": tomorrowJSON}

    # Iterate over every event
    for event in [event for dayJSON in allJSON.values() for league in dayJSON for event in league["events"]]:
        eventId = event["id"]
        homeTeam = str(event["homeTeam"]["name"])
        awayTeam = str(event["awayTeam"]["name"])
        homeScore = event["homeScore"]["current"]
        awayScore = event["awayScore"]["current"]
        minute = event["minute"]
        status = "halftime" if str(event["statusDescription"]) == "HF" else str(event["status"]["type"])
        startTimestamp = event["startTimestamp"]
        matches[eventId] = {"homeTeam": homeTeam, "awayTeam": awayTeam, "homeScore": homeScore, "awayScore": awayScore, "minute": minute, "status": status, "startTimestamp": startTimestamp}

    # Sort matches by startTimestamp
    matches = dict(OrderedDict(sorted(matches.items(), key=lambda x: getitem(x[1], 'startTimestamp'))))
    return matches


def main():
    # Set LOG_JSON, JSON_REPORT
    JSON_REPORT = getLog()
    eventIdsToRemove = []

    # Iterate over every match
    for eventId, match in getMatches().items():
        eventId = str(eventId)

        # Get match info
        homeScore, awayScore, status = match["homeScore"], match["awayScore"], match["status"]
        homeTeam, awayTeam, minute = match["homeTeam"], match["awayTeam"], match["minute"]

        # If match not in JSON_REPORT -> add
        if eventId not in JSON_REPORT and status != "finished":
            print(eventId, "ADD")
            JSON_REPORT[eventId] = match

        # If match is already in JSON_REPORT -> check for changes
        if eventId in JSON_REPORT:

            # Get LOG info
            LOG_homeScore, LOG_awayScore, LOG_status = JSON_REPORT[eventId]["homeScore"], JSON_REPORT[eventId]["awayScore"], JSON_REPORT[eventId]["status"]

            # Check if match has started
            if LOG_status == "notstarted" and status == "inprogress":
                print(eventId, "START")
                print(homeTeam, "VS", awayTeam)
                # yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "START - " + homeTeam + " VS " + awayTeam)

            # Check is match has updated score
            elif status == "inprogress" and (LOG_homeScore != homeScore or LOG_awayScore != awayScore):
                print(eventId, "SCORE")
                print(homeTeam, "VS", awayTeam, "@", minute)
                print(LOG_homeScore, "-", LOG_awayScore)
                print(homeScore, "-", awayScore)
                # yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "SCORE (" + minute + "') - " + homeTeam + "(" + homeScore + ")" + " VS " + awayTeam + "(" + awayScore + ")")

            # Check if game is half time
            elif LOG_status == "inprogress" and status == "halftime":
                print(eventId, "HALF-TIME")
                print(homeTeam, "VS", awayTeam)
                # yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "HALF-TIME - " + homeTeam + "(" + homeScore + ")" + " VS " + awayTeam + "(" + awayScore + ")")

            # Check if game has resumed
            elif LOG_status == "halftime" and status == "inprogress":
                print(eventId, "RESUMED")
                print(homeTeam, "VS", awayTeam)
                # yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "RESUMED - " + homeTeam + "(" + homeScore + ")" + " VS " + awayTeam + "(" + awayScore + ")")

            # Check if mathc has finished
            elif LOG_status == "inprogress" and status == "finished":
                print(eventId, "FULL-TIME")
                print(homeTeam, "VS", awayTeam)
                print(homeScore, "-", awayScore)
                # yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "FULL-TIME - " + homeTeam + "(" + homeScore + ")" + " VS " + awayTeam + "(" + awayScore + ")")

            # Update match on JSON_REPORT is game hasn't finished
            if status == "finished":
                eventIdsToRemove.append(eventId)
            else:
                JSON_REPORT[eventId] = match

    # Remove Finished games
    for eventId in eventIdsToRemove:
        del JSON_REPORT[eventId]

    # Sort JSON_REPORT by startTimestamp
    JSON_REPORT = dict(OrderedDict(sorted(JSON_REPORT.items(), key=lambda x: getitem(x[1], 'startTimestamp'))))

    # Save log
    with open(LOG_FILE, "w") as outFile:
        json.dump(JSON_REPORT, outFile, indent=2)


if __name__ == "__main__":
    print("----------------------------------------------------")
    print(str(datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")))

    # Set temp folder
    LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.json")

    # Check if script is already running
    procs = [proc for proc in psutil.process_iter(attrs=["cmdline"]) if os.path.basename(__file__) in '\t'.join(proc.info["cmdline"])]
    if len(procs) > 2:
        print("isRunning")
    else:
        try:
            main()
        except Exception as ex:
            print(traceback.format_exc())
            yagmail.SMTP(EMAIL_USER, EMAIL_APPPW).send(EMAIL_RECEIVER, "Error - " + os.path.basename(__file__), str(traceback.format_exc()))
        finally:
            print("End")
