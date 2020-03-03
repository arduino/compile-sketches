import logging
import argparse
import json
import datetime
from google.oauth2 import service_account
from googleapiclient import discovery

# import httplib2
# httplib2.debuglevel = 4

logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)
logger_level = logging.WARNING


def main(argument):
    set_verbosity(enable_verbosity=argument.enable_verbosity)

    report_size_trends = ReportSizeTrends(google_key_file=argument.google_key_file,
                                          spreadsheet_id=argument.spreadsheet_id,
                                          sheet_name=argument.sheet_name,
                                          sketch_name=argument.sketch_name,
                                          commit_hash=argument.commit_hash,
                                          commit_url=argument.commit_url,
                                          fqbn=argument.fqbn,
                                          flash=argument.flash,
                                          ram=argument.ram)

    report_size_trends.report_size_trends()


def set_verbosity(enable_verbosity):
    """Turn debug output on or off.

    Keyword arguments:
    enable_verbosity -- this will generally be controlled via the script's --verbose command line argument
                              (True, False)
    """
    # DEBUG: automatically generated output and all higher log level output
    # INFO: manually specified output and all higher log level output
    verbose_logging_level = logging.DEBUG

    if type(enable_verbosity) is not bool:
        raise TypeError
    if enable_verbosity:
        logger.setLevel(level=verbose_logging_level)
    else:
        logger.setLevel(level=logging.WARNING)


class ReportSizeTrends:
    """Methods for reporting memory usage to a Google Sheets spreadsheet

    Keyword arguments:
    google_key_file -- Google key file that gives write access to the Google Sheets API
    spreadsheet_id -- ID of the spreadsheet
    sheet_name -- name of the spreadsheet's sheet to use for the report
    sketch_name -- name of the example sketch the memory usage data comes from
    commit_hash -- SHA of the commit the data applies to
    commit_url -- GitHub URL for the commit
    fqbn -- FQBN of the board the data is for
    flash -- flash memory usage of the sketch when compiled for the FQBN
    ram -- dynamic memory used by globals of the sketch when compiled for the FQBN
    """
    heading_row_number = "1"
    timestamp_column_letter = "A"
    timestamp_column_heading = "Commit Timestamp"
    sketch_name_column_letter = "B"
    sketch_name_column_heading = "Sketch Name"
    commit_hash_column_letter = "C"
    commit_hash_column_heading = "Commit Hash"
    shared_data_first_column_letter = timestamp_column_letter
    shared_data_last_column_letter = commit_hash_column_letter
    shared_data_columns_headings_data = (
            "[[\"" + timestamp_column_heading + "\",\"" + sketch_name_column_heading + "\",\"" +
            commit_hash_column_heading + "\"]]")

    # These are appended to the FQBN as the size data column headings
    flash_heading_indicator = " flash"
    ram_heading_indicator = " RAM"

    def __init__(self, google_key_file, spreadsheet_id, sheet_name, sketch_name, commit_hash, commit_url, fqbn, flash,
                 ram):
        self.google_key_file = google_key_file
        self.sheet_name = sheet_name
        self.spreadsheet_id = spreadsheet_id
        self.fqbn = fqbn
        self.commit_hash = commit_hash
        self.sketch_name = sketch_name
        self.commit_url = commit_url
        self.flash = flash
        self.ram = ram

    def report_size_trends(self):
        """Add memory usage data to a Google Sheets spreadsheet"""
        self.service = self.get_service(google_key_file=self.google_key_file)

        heading_row_data = self.get_heading_row_data()

        if ("values" in heading_row_data) is False:
            # Fresh sheet, so fill in the shared data headings
            logger.info("Initializing empty sheet")
            self.populate_shared_data_headings()

            # Get the heading row data again in case it changed
            heading_row_data = self.get_heading_row_data()

        data_column_letters = self.get_data_column_letters(heading_row_data=heading_row_data)

        if not data_column_letters["populated"]:
            # Columns don't exist for this board yet, so create them
            self.populate_data_column_headings(flash_column_letter=data_column_letters["flash"],
                                               ram_column_letter=data_column_letters["ram"])

        current_row = self.get_current_row()

        if not current_row["populated"]:
            # A row doesn't exist for this commit yet, so create one
            self.create_row(row_number=current_row["number"])

        self.write_memory_usage_data(flash_column_letter=data_column_letters["flash"],
                                     ram_column_letter=data_column_letters["ram"],
                                     row_number=current_row["number"],
                                     flash=self.flash,
                                     ram=self.ram)

    def get_service(self, google_key_file):
        """Return the Google API service object

        Keyword arguments:
        google_key_file -- contents of the Google private key file
        """
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(google_key_file, strict=False), scopes=['https://www.googleapis.com/auth/spreadsheets'])
        return discovery.build('sheets', 'v4', credentials=credentials)

    def get_heading_row_data(self):
        """Return the contents of the heading row"""
        spreadsheet_range = self.sheet_name + "!" + self.heading_row_number + ":" + self.heading_row_number
        request = self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id, range=spreadsheet_range)
        response = request.execute()
        logger.debug("heading_row_data: ")
        logger.debug(response)
        return response

    def populate_shared_data_headings(self):
        """Add the headings to the shared data columns (timestamp, sketch name, commit)"""
        spreadsheet_range = (
                self.sheet_name + "!" + self.shared_data_first_column_letter + self.heading_row_number + ":" +
                self.shared_data_last_column_letter + self.heading_row_number)
        request = self.service.spreadsheets().values().update(spreadsheetId=self.spreadsheet_id,
                                                              range=spreadsheet_range,
                                                              valueInputOption="RAW",
                                                              body={"values": json.loads(
                                                                  self.shared_data_columns_headings_data)})
        response = request.execute()
        logger.debug(response)

    def get_data_column_letters(self, heading_row_data):
        """Return a dictionary containing the data column numbers for the board
        populated -- whether the column headings have been added
        flash -- letter of the column containing flash usage data
        ram -- letter of the column containing ram usage data

        Keyword arguments:
        heading_row_data -- the contents of the heading row of the spreadsheet, as returned by get_heading_row_data()
        """
        populated = False
        index = 0
        for index, cell_text in enumerate(heading_row_data["values"][0]):
            if cell_text == self.fqbn + self.flash_heading_indicator:
                populated = True
                break

        if not populated:
            # Use the next columns
            index += 1

        board_data_flash_column_letter = chr(index + 65)
        board_data_ram_column_letter = chr(index + 1 + 65)
        logger.info("Flash data column: " + board_data_flash_column_letter)
        logger.info("RAM data column: " + board_data_ram_column_letter)
        return {"populated": populated, "flash": board_data_flash_column_letter, "ram": board_data_ram_column_letter}

    def populate_data_column_headings(self, flash_column_letter, ram_column_letter):
        """Add the headings to the data columns for this FQBN

        Keyword arguments:
        flash_column_letter -- letter of the column that contains the flash usage data
        ram_column_letter -- letter of the column that contains the dynamic memory used by globals data
        """
        logger.info("No data columns found for " + self.fqbn + ". Adding column headings at columns " +
                    flash_column_letter + " and " + ram_column_letter)
        spreadsheet_range = (self.sheet_name + "!" + flash_column_letter + self.heading_row_number + ":" +
                             ram_column_letter + self.heading_row_number)
        board_data_headings_data = ("[[\"" + self.fqbn + self.flash_heading_indicator + "\",\"" + self.fqbn +
                                    self.ram_heading_indicator + "\"]]")
        request = self.service.spreadsheets().values().update(spreadsheetId=self.spreadsheet_id,
                                                              range=spreadsheet_range,
                                                              valueInputOption="RAW",
                                                              body={"values": json.loads(board_data_headings_data)})
        response = request.execute()
        logger.debug(response)

    def get_current_row(self):
        """Return a dictionary for the current row:
        populated -- whether the shared data has already been added to the row
        number -- the row number
        """
        spreadsheet_range = (self.sheet_name + "!" + self.commit_hash_column_letter + ":" +
                             self.commit_hash_column_letter)
        request = self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id,
                                                           range=spreadsheet_range)
        commit_hash_column_data = request.execute()
        logger.debug(commit_hash_column_data)

        populated = False
        index = 0
        for index, cell_text in enumerate(commit_hash_column_data["values"], start=1):
            if cell_text[0] == self.commit_hash:
                populated = True
                break

        if not populated:
            index += 1

        logger.info("Current row number: " + str(index))
        return {"populated": populated, "number": index}

    def create_row(self, row_number):
        """Add the shared data to the row

        Keyword arguments:
        row_number -- row number
        """
        logger.info("No row found for the commit hash: " + self.commit_hash + ". Creating a new row #" +
                    str(row_number))
        spreadsheet_range = (self.sheet_name + "!" + self.shared_data_first_column_letter + str(row_number) +
                             ":" + self.shared_data_last_column_letter + str(row_number))
        shared_data_columns_data = ("[[\"" + "{:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now()) + "\",\"" +
                                    self.sketch_name + "\",\"=HYPERLINK(\\\"" + self.commit_url + "\\\",T(\\\"" +
                                    self.commit_hash + "\\\"))\"]]")
        request = self.service.spreadsheets().values().update(spreadsheetId=self.spreadsheet_id,
                                                              range=spreadsheet_range,
                                                              valueInputOption="USER_ENTERED",
                                                              body={"values": json.loads(shared_data_columns_data)})
        response = request.execute()
        logger.debug(response)

    def write_memory_usage_data(self, flash_column_letter, ram_column_letter, row_number, flash, ram):
        """Write the memory usage data for the board to the spreadsheet

        Keyword arguments:
        flash_column_letter -- letter of the column containing flash memory usage data for the board
        ram_column_letter -- letter of the column containing dynamic memory used for global variables for the board
        row_number -- number of the row to write to
        flash -- flash usage
        ram -- dynamic memory used for global variables
        """
        spreadsheet_range = (self.sheet_name + "!" + flash_column_letter + str(row_number) + ":" +
                             ram_column_letter + str(row_number))
        size_data = "[[" + flash + "," + ram + "]]"
        request = self.service.spreadsheets().values().update(spreadsheetId=self.spreadsheet_id,
                                                              range=spreadsheet_range,
                                                              valueInputOption="RAW",
                                                              body={"values": json.loads(size_data)})
        response = request.execute()
        logger.debug(response)


# Only execute the following code if the script is run directly, not imported
if __name__ == '__main__':
    # Parse command line arguments
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--google-key-file", dest="google_key_file",
                                 help="Contents of the Google authentication key file")
    argument_parser.add_argument("--spreadsheet-id", dest="spreadsheet_id",
                                 help="ID of the Google Sheets spreadsheet to edit")
    argument_parser.add_argument("--sheet-name", dest="sheet_name",
                                 help="Sheet name of the Google Sheets spreadsheet to edit")
    argument_parser.add_argument("--sketch-name", dest="sketch_name",
                                 help="Name of the sketch the size data is from")
    argument_parser.add_argument("--commit-hash", dest="commit_hash",
                                 help="Commit hash the size data is for")
    argument_parser.add_argument("--commit-url", dest="commit_url",
                                 help="URL of the commit")
    argument_parser.add_argument("--fqbn", dest="fqbn",
                                 help="FQBN of the board being compiled for")
    argument_parser.add_argument("--flash", dest="flash",
                                 help="Flash usage of the sketch")
    argument_parser.add_argument("--ram", dest="ram",
                                 help="RAM usage for global variables of the sketch")
    argument_parser.add_argument("--verbose", dest="enable_verbosity", help="Enable verbose output",
                                 action="store_true")

    # Run program
    main(argument_parser.parse_args())
