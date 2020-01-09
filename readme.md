# GameDjinnie
Bot for managing game codes and testing through discord!

## Adding a game
This will add a game to the bot, needed before you can add codes and test the game
``!add_game <name>``


## Adding codes
This will add codes for a game to the bot to be given to testers during testing. The message needs to have an attachment of a single txt file containing the codes, 1 code per line
``!add_codes <game_name>``


## Removing codes
If you assigned codes to the wrong game or want the bot to forget these codes exist for some reason. The message needs to have an attachment of a single txt file containing the codes, 1 code per line
``!remove_codes <game_name>``

## Running a test
This pings the testers for the test and allows them to claim codes through the bot. **Dates need to be wrapped with ``"``!** Dates can contain an exact time to stop, for example ``"2020/01/09 18:00"``. The format of <year>/<month>/<day> <hour>:<minutes> is highly recommended to avoid ambiguity
``!test <game_name> <until> <sheet_url> <announcement>``

##List running tests
Lists all active tests and how long aprox until they end
``!running``

## altering the test end time/date
Changes the scheduled time for a test to end. Test_message_id is the id of the message it send in the announcements channel for that test.
``!update_end_time <test_message_id> <new_time>``

## altering the test announcement content
Updates the test announcement, testers are not pinged again.
``!update <test_message_id> <new_message>``

## Testing report
Gets a report with all testers who signed up for a test, how many times they filled in the feedback form and the code their received
``!test_report <test_message_id>``

## Inactivity report
Gives a list of all people who did not submit feedback in the last x tests (regardless on if they signed up for those tests or not)
``!inactive_report <test_count>``