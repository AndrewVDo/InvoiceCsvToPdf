# Read CSV with the following data columns
# Booking Date, Date Appointment, Name, Email, Phone, Description, Deposit, Flat Rate, Rate, Hours
import pandas as pd
import math
import numbers
from PyPDF2 import PdfWriter, PdfReader
import io
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter

class RowWriter:
    static_sum = 0
    row = None
    packet = None
    canvas = None
    

    def __init__(self, row):
        self.row = row
        self.initCanvas()
        self.drawHeader()
        self.drawItemized()
        self.Export()

    def initCanvas(self):
        self.packet = io.BytesIO()
        self.canvas = Canvas(self.packet, pagesize=letter)
        self.canvas.setFont("Helvetica", 8)

    def getData(self, rowName, isDollar=False):
        data = self.row[rowName]
        display = ""
        if isinstance(data, numbers.Number):
            if not math.isnan(data):
                if isDollar:
                    display = "${:.2f}".format(data)
                else:
                    display = "{}".format(data)
        else:
            display = "{}".format(data)
        return display

    def getDescription(self):
        rawDescription = self.getData("description")
        display = "tattoo"
        if rawDescription != "":
            display = "{} tattoo".format(rawDescription)
        return display

    def getDate(self, rowName, year=2022):
        date = self.getData(rowName)
        if date == "":
            return ""
        else:
            return "{} {}".format(self.getData(rowName), year) 

    def getBestAppointmentDate(self):
        date = self.getDate('appointment_date')
        if len(date) > 0:
            return date
        else:
            return self.getDate('booking_date')

    def draw(self, x, y, string, asRowName=True, isDollar=False):
        if asRowName:
            self.canvas.drawString(x, y, self.getData(string, isDollar=isDollar))
        else:
            self.canvas.drawString(x, y, string)

    def drawHeader(self):
        self.draw(165, 610, 'invoice_number')
        self.draw(165, 585, self.getDate('booking_date'), asRowName=False)

        self.draw(395, 610, 'name')
        self.draw(395, 585, 'email')
        self.draw(400, 560, 'phone')

        self.draw(160, 250, self.getBestAppointmentDate(), asRowName=False)

        self.draw(430, 250, 'subtotal', isDollar=True)
        self.draw(430, 225, '$0.00', asRowName=False)
        self.draw(430, 200, 'subtotal', isDollar=True)

        RowWriter.static_sum += float(self.getData('subtotal'))

    def drawItemized(self):
        itemizedList = []
        if not math.isnan(self.row['deposit']):
            desc = "Deposit for {}.".format(self.getDescription())
            date = self.getDate('booking_date')
            amnt = self.getData('deposit', isDollar=True)
            itemizedList.append([desc, date, "", amnt])

        if self.row['rebate_deposit']:
            desc = "Deposit credit for {}.".format(self.getDescription())
            date = self.getBestAppointmentDate()
            amnt = "-{}".format(self.getData('deposit', isDollar=True))
            itemizedList.append([desc, date, "", amnt])

        if not math.isnan(self.row['flat_rate']):
            desc = "Flat charge for {}.".format(self.getDescription())
            date = self.getBestAppointmentDate()
            amnt = self.getData('flat_rate', isDollar=True)
            itemizedList.append([desc, date, "", amnt])

        if not math.isnan(self.row['hours']) and math.isnan(self.row['flat_rate']):
            desc = "Hourly charge for {} @{} hours.".format(self.getDescription(), self.getData('hours'))
            date = self.getBestAppointmentDate()
            rate = "$180.00"
            amnt = "${:.2f}".format(self.row['hours'] * self.row['hourly_rate'])
            itemizedList.append([desc, date, rate, amnt])
        
        columnXs = [80, 300, 420, 470]
        currentY = 500
        for item in itemizedList:
            for col in range(4):
                self.draw(columnXs[col], currentY, item[col], asRowName=False)
            currentY -= 15

    def Export(self, outDir="output/", baseFile="invoice.pdf"):
        self.canvas.save()
        self.packet.seek(0)
        drawnPdf = PdfReader(self.packet)
        basePdf = PdfReader(open(baseFile, "rb"))
        output = PdfWriter()

        page = basePdf.pages[0]
        page.merge_page(drawnPdf.pages[0])
        output.add_page(page)

        output_stream = open("{}/INVOICE_{}.pdf".format(outDir, self.row['invoice_number']), "wb")
        output.write(output_stream)
        output_stream.close()


class TaxWrapper:
    data = None
    writer = None

    def __init__(self, filename):
        self.readCSV(filename)
        # self.showSummary()
        print("Processing Data...")
        self.calculateInvoiceNumberColumn()
        self.calculateRebateColumn()
        self.calculateSubtotalColumn()
        print("Done.")
        # self.findDuplicateNames()
        # self.showSummary()
        self.createPDFs()

    def findDuplicateNames(self):
        names = {}
        dupe = []
        for index, row in self.data.iterrows():
            if row['name'] in names:
                names[row['name']] += 1
            else:
                names[row['name']] = 1
        for name in names:
            if names[name] > 1:
                dupe.append(name)
        print(dupe)

    def readCSV(self, filename):
        self.data = pd.read_csv(filename)

    def showSummary(self):
        print(self.data.info())

    def createPDFs(self):
        print("Creating PDFS...")
        for index, _ in self.data.iterrows():
            RowWriter(self.data.iloc[index])
        print("Done.")

    def calculateInvoiceNumberColumn(self, year="2022"):
        self.data.reset_index()
        invoiceNumberList = []
        totalNumDigits = 12 - len(year)
        for index, _ in self.data.iterrows():
            numZeroFill = totalNumDigits - len(str(index))
            invoiceNumberList.append(year + ("0" * numZeroFill) + str(index))
        self.data['invoice_number'] = invoiceNumberList

    def calculateRebateColumn(self):
        self.data.reset_index()
        rebateList = []
        for index, row in self.data.iterrows():
            if not math.isnan(row['deposit']) and (not math.isnan(row['flat_rate']) or (not math.isnan(row['hourly_rate']) and not math.isnan(row['hours']))):
                rebateList.append(True)
            else:
                rebateList.append(False)
        self.data['rebate_deposit'] = rebateList
        
    def calculateSubtotalColumn(self):
        self.data.reset_index()
        subtotalList = []
        errorList = []
        for index, row in self.data.iterrows():
            if not math.isnan(row['flat_rate']):
                # flat rates are usually given as a total so deposits are credited
                subtotalList.append(row['flat_rate'])
            elif not math.isnan(row['hourly_rate']) and not math.isnan(row['hours']):
                # hourly rates are usually given as a total so deposits are credited
                subtotalList.append(row['hourly_rate'] * row['hours'])
            elif not math.isnan(row['deposit']):
                # if it has reached this point then it's most likely a cancellation and the deposit is the sub total
                subtotalList.append(row['deposit'])
            else:
                subtotalList.append(0)
                errorList.append(index)
                # print("Error at Row {}: {}".format(index, row))
        # if len(errorList) > 0:
        # else:
        self.data['subtotal'] = subtotalList


def main():
    data = TaxWrapper('data.csv')
    print("Total: {}".format(RowWriter.static_sum))

if __name__ == "__main__":
    main()

