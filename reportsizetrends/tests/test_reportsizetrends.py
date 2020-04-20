import unittest.mock
from reportsizetrends import *


# Stub
class Service:
    x = 0

    def spreadsheets(self):
        self.x = 42
        return Service()

    def values(self):
        self.x = 42
        return Service()


# noinspection PyUnresolvedReferences
class TestReportsizetrends(unittest.TestCase):
    set_verbosity(enable_verbosity=False)

    # @unittest.skip("")
    def test_set_verbosity(self):
        with self.assertRaises(TypeError):
            set_verbosity(enable_verbosity=2)
        set_verbosity(enable_verbosity=True)
        set_verbosity(enable_verbosity=False)

    # @unittest.skip("")
    def test_report_size_trends(self):
        google_key_file = "test_google_key_file"
        flash = 42
        ram = 11
        heading_row_data = {}
        current_row = {"populated": False, "number": 42}
        data_column_letters = {"populated": False, "flash": "A", "ram": "B"}
        report_size_trends = ReportSizeTrends(google_key_file=google_key_file,
                                              spreadsheet_id="foo",
                                              sheet_name="foo",
                                              sketch_name="foo",
                                              commit_hash="foo",
                                              commit_url="foo",
                                              fqbn="foo",
                                              flash=flash,
                                              ram=ram)

        report_size_trends.get_service = unittest.mock.MagicMock()
        report_size_trends.get_heading_row_data = unittest.mock.MagicMock(return_value=heading_row_data)
        report_size_trends.populate_shared_data_headings = unittest.mock.MagicMock()
        report_size_trends.get_data_column_letters = unittest.mock.MagicMock(return_value=data_column_letters)
        report_size_trends.populate_data_column_headings = unittest.mock.MagicMock()
        report_size_trends.get_current_row = unittest.mock.MagicMock(return_value=current_row)
        report_size_trends.create_row = unittest.mock.MagicMock()
        report_size_trends.write_memory_usage_data = unittest.mock.MagicMock()

        # Test unpopulated shared data headings
        report_size_trends.report_size_trends()

        report_size_trends.get_service.assert_called_once_with(google_key_file=google_key_file)
        report_size_trends.get_heading_row_data.assert_has_calls([unittest.mock.call(), unittest.mock.call()])
        report_size_trends.populate_shared_data_headings.assert_called_once()
        report_size_trends.get_data_column_letters.assert_called_once_with(heading_row_data=heading_row_data)
        report_size_trends.populate_data_column_headings.assert_called_once_with(
            flash_column_letter=data_column_letters["flash"],
            ram_column_letter=data_column_letters["ram"]
        )
        report_size_trends.get_current_row.assert_called_once()
        report_size_trends.create_row.assert_called_once_with(row_number=current_row["number"])
        report_size_trends.write_memory_usage_data.assert_called_once_with(
            flash_column_letter=data_column_letters["flash"],
            ram_column_letter=data_column_letters["ram"],
            row_number=current_row["number"],
            flash=flash,
            ram=ram)

        # Test populated shared data headings
        heading_row_data = {"values": "foo"}
        report_size_trends.get_heading_row_data = unittest.mock.MagicMock(return_value=heading_row_data)
        report_size_trends.populate_shared_data_headings.reset_mock()
        report_size_trends.report_size_trends()
        report_size_trends.populate_shared_data_headings.assert_not_called()

        # Test pre-populated data column headings
        data_column_letters["populated"] = True
        report_size_trends.get_data_column_letters = unittest.mock.MagicMock(return_value=data_column_letters)
        report_size_trends.populate_data_column_headings.reset_mock()
        report_size_trends.report_size_trends()
        report_size_trends.populate_data_column_headings.assert_not_called()

        # Test pre-populated row
        current_row["populated"] = True
        report_size_trends.get_current_row = unittest.mock.MagicMock(return_value=current_row)
        report_size_trends.create_row.reset_mock()
        report_size_trends.report_size_trends()
        report_size_trends.create_row.assert_not_called()

    # @unittest.skip("")
    def test_get_heading_row_data(self):
        spreadsheet_id = "test_spreadsheet_id"
        sheet_name = "test_sheet_name"
        report_size_trends = ReportSizeTrends(google_key_file="foo",
                                              spreadsheet_id=spreadsheet_id,
                                              sheet_name=sheet_name,
                                              sketch_name="foo",
                                              commit_hash="foo",
                                              commit_url="foo",
                                              fqbn="foo",
                                              flash=42,
                                              ram=11)
        heading_row_data = "test_heading_row_data"

        Service.get = unittest.mock.MagicMock(return_value=Service())
        Service.execute = unittest.mock.MagicMock(return_value=heading_row_data)
        report_size_trends.service = Service()

        self.assertEqual(heading_row_data, report_size_trends.get_heading_row_data())
        spreadsheet_range = (sheet_name + "!" + report_size_trends.heading_row_number + ":" +
                             report_size_trends.heading_row_number)
        Service.get.assert_called_once_with(spreadsheetId=spreadsheet_id, range=spreadsheet_range)
        Service.execute.assert_called_once()

    # @unittest.skip("")
    def test_populate_shared_data_headings(self):
        spreadsheet_id = "test_spreadsheet_id"
        sheet_name = "test_sheet_name"
        report_size_trends = ReportSizeTrends(google_key_file="foo",
                                              spreadsheet_id=spreadsheet_id,
                                              sheet_name=sheet_name,
                                              sketch_name="foo",
                                              commit_hash="foo",
                                              commit_url="foo",
                                              fqbn="foo",
                                              flash=42,
                                              ram=11)

        Service.update = unittest.mock.MagicMock(return_value=Service())
        Service.execute = unittest.mock.MagicMock()
        report_size_trends.service = Service()

        report_size_trends.populate_shared_data_headings()
        spreadsheet_range = (
            sheet_name + "!" + report_size_trends.shared_data_first_column_letter +
            report_size_trends.heading_row_number + ":" + report_size_trends.shared_data_last_column_letter +
            report_size_trends.heading_row_number
        )
        Service.update.assert_called_once_with(
            spreadsheetId=spreadsheet_id,
            range=spreadsheet_range,
            valueInputOption="RAW",
            body={"values": json.loads(
                report_size_trends.shared_data_columns_headings_data)}
        )
        Service.execute.assert_called_once()

    # @unittest.skip("")
    def test_get_data_column_letters(self):
        fqbn = "test_fqbn"

        report_size_trends = ReportSizeTrends(google_key_file="foo",
                                              spreadsheet_id="foo",
                                              sheet_name="foo",
                                              sketch_name="foo",
                                              commit_hash="foo",
                                              commit_url="foo",
                                              fqbn=fqbn,
                                              flash=42,
                                              ram=11)
        heading_row_data = {"values": [["foo", "bar"]]}
        column_letters = report_size_trends.get_data_column_letters(heading_row_data)
        self.assertEqual(False, column_letters["populated"])
        self.assertEqual("C", column_letters["flash"])
        self.assertEqual("D", column_letters["ram"])

        heading_row_data = {"values": [["foo", report_size_trends.fqbn + report_size_trends.flash_heading_indicator]]}
        column_letters = report_size_trends.get_data_column_letters(heading_row_data)
        self.assertEqual(True, column_letters["populated"])
        self.assertEqual("B", column_letters["flash"])
        self.assertEqual("C", column_letters["ram"])

    # @unittest.skip("")
    def test_populate_data_column_headings(self):
        spreadsheet_id = "test_spreadsheet_id"
        sheet_name = "test_sheet_name"
        fqbn = "test_fqbn"
        report_size_trends = ReportSizeTrends(google_key_file="foo",
                                              spreadsheet_id=spreadsheet_id,
                                              sheet_name=sheet_name,
                                              sketch_name="foo",
                                              commit_hash="foo",
                                              commit_url="foo",
                                              fqbn=fqbn,
                                              flash=42,
                                              ram=11)
        flash_column_letter = "A"
        ram_column_letter = "B"

        Service.update = unittest.mock.MagicMock(return_value=Service())
        Service.execute = unittest.mock.MagicMock()
        report_size_trends.service = Service()

        report_size_trends.populate_data_column_headings(flash_column_letter=flash_column_letter,
                                                         ram_column_letter=ram_column_letter)
        spreadsheet_range = (sheet_name + "!" + flash_column_letter + report_size_trends.heading_row_number + ":" +
                             ram_column_letter + report_size_trends.heading_row_number)
        board_data_headings_data = ("[[\"" + fqbn + report_size_trends.flash_heading_indicator + "\",\"" + fqbn +
                                    report_size_trends.ram_heading_indicator + "\"]]")
        Service.update.assert_called_once_with(spreadsheetId=spreadsheet_id,
                                               range=spreadsheet_range,
                                               valueInputOption="RAW",
                                               body={"values": json.loads(board_data_headings_data)})
        Service.execute.assert_called_once()

    # @unittest.skip("")
    def test_get_current_row(self):
        spreadsheet_id = "test_spreadsheet_id"
        sheet_name = "test_sheet_name"
        commit_hash = "test_commit_hash"
        report_size_trends = ReportSizeTrends(google_key_file="foo",
                                              spreadsheet_id=spreadsheet_id,
                                              sheet_name=sheet_name,
                                              sketch_name="foo",
                                              commit_hash=commit_hash,
                                              commit_url="foo",
                                              fqbn="foo",
                                              flash=42,
                                              ram=11)
        Service.get = unittest.mock.MagicMock(return_value=Service())
        Service.execute = unittest.mock.MagicMock(return_value={"values": [["foo"], [commit_hash]]})
        report_size_trends.service = Service()

        self.assertEqual({"populated": True, "number": 2}, report_size_trends.get_current_row())
        spreadsheet_range = (sheet_name + "!" + report_size_trends.commit_hash_column_letter + ":" +
                             report_size_trends.commit_hash_column_letter)
        Service.get.assert_called_once_with(spreadsheetId=spreadsheet_id, range=spreadsheet_range)
        Service.execute.assert_called_once()
        Service.execute = unittest.mock.MagicMock(return_value={"values": [["foo"], ["bar"]]})
        self.assertEqual({"populated": False, "number": 3}, report_size_trends.get_current_row())

    # @unittest.skip("")
    def test_create_row(self):
        spreadsheet_id = "test_spreadsheet_id"
        sheet_name = "test_sheet_name"
        sketch_name = "test_sketch_name"
        fqbn = "test_fqbn"
        commit_url = "test_commit_url"
        report_size_trends = ReportSizeTrends(google_key_file="foo",
                                              spreadsheet_id=spreadsheet_id,
                                              sheet_name=sheet_name,
                                              sketch_name=sketch_name,
                                              commit_hash="foo",
                                              commit_url=commit_url,
                                              fqbn=fqbn,
                                              flash=42,
                                              ram=11)
        row_number = 42

        Service.update = unittest.mock.MagicMock(return_value=Service())
        Service.execute = unittest.mock.MagicMock()
        report_size_trends.service = Service()

        report_size_trends.create_row(row_number=row_number)
        spreadsheet_range = (sheet_name + "!" + report_size_trends.shared_data_first_column_letter + str(row_number) +
                             ":" + report_size_trends.shared_data_last_column_letter + str(row_number))
        shared_data_columns_data = ("[[\"" + '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()) + "\",\"" +
                                    sketch_name + "\",\"=HYPERLINK(\\\"" + report_size_trends.commit_url +
                                    "\\\",T(\\\"" + report_size_trends.commit_hash + "\\\"))\"]]")
        Service.update.assert_called_once_with(spreadsheetId=spreadsheet_id,
                                               range=spreadsheet_range,
                                               valueInputOption="USER_ENTERED",
                                               body={"values": json.loads(shared_data_columns_data)})
        Service.execute.assert_called_once()

    # @unittest.skip("")
    def test_write_memory_usage_data(self):
        spreadsheet_id = "test_spreadsheet_id"
        sheet_name = "test_sheet_name"
        report_size_trends = ReportSizeTrends(google_key_file="foo",
                                              spreadsheet_id=spreadsheet_id,
                                              sheet_name=sheet_name,
                                              sketch_name="foo",
                                              commit_hash="foo",
                                              commit_url="foo",
                                              fqbn="foo",
                                              flash=42,
                                              ram=11)
        flash_column_letter = "A"
        ram_column_letter = "B"
        row_number = 42
        flash = "11"
        ram = "12"

        Service.update = unittest.mock.MagicMock(return_value=Service())
        Service.execute = unittest.mock.MagicMock()
        report_size_trends.service = Service()

        report_size_trends.write_memory_usage_data(flash_column_letter=flash_column_letter,
                                                   ram_column_letter=ram_column_letter,
                                                   row_number=row_number, flash=flash, ram=ram)
        spreadsheet_range = (sheet_name + "!" + flash_column_letter + str(row_number) + ":" +
                             ram_column_letter + str(row_number))
        size_data = "[[" + flash + "," + ram + "]]"
        Service.update.assert_called_once_with(spreadsheetId=spreadsheet_id,
                                               range=spreadsheet_range,
                                               valueInputOption="RAW",
                                               body={"values": json.loads(size_data)})
        Service.execute.assert_called_once()


if __name__ == '__main__':
    unittest.main()
