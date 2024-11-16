require("dotenv").config();
const express = require("express");
const app = express();
const bodyParser = require("body-parser");
const mongoose = require("mongoose");
const cors = require("cors");
const path = require("path");
const cookieParser = require('cookie-parser');

// node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
//local imports
const port = process.env.PORT || 8000;
const connectionString = process.env.CONNECTIONSTRING; 
const loginRoute = require("./server/routes/loginRoute");
const registerRoute = require("./server/routes/registerRoute");
const dashboardRoute = require("./server/routes/dashboardRoute");

//database connection
mongoose.connect(connectionString);
const database = mongoose.connection;
database.on("error", () => {console.log("Failed to connect to database")});
database.once("open", () => {console.log("Successful connection to database")});

//middleware
app.use(cookieParser());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({extended: true}));

//cors middleware to accept requests.
const allowedOrigins = ['http://localhost:3000', 'http://localhost:5000'];
const corsOptions = {
  origin: function (origin, callback) {
    if (!origin || allowedOrigins.indexOf(origin) !== -1) {
      callback(null, true);
    } else {
      callback(new Error('Not allowed by CORS'));
    }
  },
  credentials: true,
  optionsSuccessStatus: 200
};

app.use(cors(corsOptions));

app.use(express.static(path.join(__dirname, 'src')));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'src'));

//routes
app.use('', loginRoute);
app.use('', registerRoute);
app.use('', dashboardRoute);


//server
app.listen(port, () => {
    console.log(`running on PORT: ${port}`);
    console.log('http://localhost:3000/login')
});