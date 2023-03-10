# -*- coding: utf-8 -*-
# !/usr/bin/python3

# python3 -m pip install yagmail psutil python-telegram-bot --no-cache-dir

import datetime
import json
import os
import time
import traceback
import psutil
import requests
import random
import yagmail
from collections import OrderedDict
from operator import getitem
from telegram import Bot
from Misc import get911

EMAIL_USER = get911('EMAIL_USER')
EMAIL_APPPW = get911('EMAIL_APPPW')
EMAIL_RECEIVER = get911('EMAIL_RECEIVER')
TELEGRAM_TOKEN = get911('TELEGRAM_TOKEN')
TELEGRAM_USER_ID = get911('TELEGRAM_USER_ID')


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
    try:
        yesterday = datetime.datetime.strftime(datetime.datetime.now() - datetime.timedelta(1), "%Y-%m-%d")
        yesterdayJSON = json.loads(requests.get("https://sportscentral.io/new-api/matches?date=" + yesterday).content)
        time.sleep(random.randint(3, 9))

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        todayJSON = json.loads(requests.get("https://sportscentral.io/new-api/matches?date=" + today).content)
        time.sleep(random.randint(3, 9))

        tomorrow = datetime.datetime.strftime(datetime.datetime.now() + datetime.timedelta(1), "%Y-%m-%d")
        tomorrowJSON = json.loads(requests.get("https://sportscentral.io/new-api/matches?date=" + tomorrow).content)
        allJSON = {"yesterday": yesterdayJSON, "today": todayJSON, "tomorrow": tomorrowJSON}
    except Exception as ex:
        return {}

    # Iterate over every event
    # for event in [event for dayJSON in allJSON.values() for league in dayJSON for event in league["events"]]:
    for dayJSON in allJSON.values():
        for league in dayJSON:
            for event in league["events"]:
                eventId = event["id"]
                leagueName = league["name"]
                homeTeam = str(event["homeTeam"]["name"])
                awayTeam = str(event["awayTeam"]["name"])
                homeScore = event["homeScore"]["current"]
                awayScore = event["awayScore"]["current"]
                minute = event["minute"]
                status = "halftime" if str(event["statusDescription"]) == "HF" else str(event["status"]["type"])
                startTimestamp = event["startTimestamp"]
                matches[eventId] = {"leagueName": leagueName, "homeTeam": homeTeam, "awayTeam": awayTeam, "homeScore": homeScore, "awayScore": awayScore, "minute": minute, "status": status, "startTimestamp": startTimestamp}

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
        homeScore, awayScore, status, leagueName = match["homeScore"], match["awayScore"], match["status"], match["leagueName"]
        homeTeam, awayTeam, minute = match["homeTeam"], match["awayTeam"], match["minute"]
        messageText = False

        # If match not in JSON_REPORT -> add
        if eventId not in JSON_REPORT and status != "finished":
            print(eventId, "ADD")
            match["messageId"] = False
            JSON_REPORT[eventId] = match

        # If match is already in JSON_REPORT -> check for changes
        if eventId in JSON_REPORT:

            # Check for LOG_messageId
            try:
                LOG_messageId = JSON_REPORT[eventId]["messageId"]
                match["messageId"] = LOG_messageId
            except KeyError:
                LOG_messageId = False

            # Get LOG info
            LOG_homeScore, LOG_awayScore, LOG_status = JSON_REPORT[eventId]["homeScore"], JSON_REPORT[eventId]["awayScore"], JSON_REPORT[eventId]["status"]

            # Check if match has started
            if LOG_status == "notstarted" and status == "inprogress":
                print(eventId, "KICK-OFF")
                print("League:", leagueName)
                print(homeTeam, "VS", awayTeam)
                messageText = "KICK-OFF" + "\n" + "League: " + leagueName + "\n" + homeTeam + " VS " + awayTeam

            # Check is match has updated score
            elif status == "inprogress" and (LOG_homeScore != homeScore or LOG_awayScore != awayScore):
                print(eventId, "GOOOOAL")
                print(homeTeam, "VS", awayTeam)
                print("Minute:", minute)
                print(LOG_homeScore, "-", LOG_awayScore)
                print(homeScore, "-", awayScore)
                messageText = "GOOOOAL" + "\n" + homeTeam + " VS " + awayTeam + "\n" + "Minute: " + str(minute) + "\n" + "SCORE: " + str(homeScore) + " - " + str(awayScore)

            # Check if game is half time
            elif LOG_status == "inprogress" and status == "halftime":
                print(eventId, "HALF-TIME")
                print(homeTeam, "VS", awayTeam)
                print("SCORE", homeScore, "-", awayScore)
                messageText = "HALF-TIME" + "\n" + homeTeam + " VS " + awayTeam + "\n" + "SCORE: " + str(homeScore) + " - " + str(awayScore)

            # Check if game has resumed
            elif LOG_status == "halftime" and status == "inprogress":
                print(eventId, "RESTARTED")
                print(homeTeam, "VS", awayTeam)
                print("SCORE", homeScore, "-", awayScore)
                messageText = "RESTARTED" + "\n" + homeTeam + " VS " + awayTeam + "\n" + "SCORE: " + str(homeScore) + " - " + str(awayScore)

            # Check if mathc has finished
            elif LOG_status == "inprogress" and status == "finished":
                print(eventId, "FULL-TIME")
                print(homeTeam, "VS", awayTeam)
                print("SCORE", homeScore, "-", awayScore)
                messageText = "FULL-TIME" + "\n" + homeTeam + " VS " + awayTeam + "\n" + "SCORE: " + str(homeScore) + " - " + str(awayScore)

            if messageText:
                telegramBot = Bot(TELEGRAM_TOKEN)
                message = telegramBot.send_message(text=messageText, chat_id=TELEGRAM_USER_ID, reply_to_message_id=LOG_messageId)
                print(message["message_id"])
                match["messageId"] = message["message_id"]

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

    # Set LOG_FILES
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
