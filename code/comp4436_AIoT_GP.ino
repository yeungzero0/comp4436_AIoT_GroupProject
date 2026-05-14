int const trigPin = 2;
int const echoPin = 3;
int Duration;
int Distance;

int const trigPin2 = 4;
int const echoPin2 = 5;
int Duration2;
int Distance2;

int const trigPin3 = 6;
int const echoPin3 = 7;
int Duration3;
int Distance3;

int count = 0;
int count2 = 0;
int count3 = 0;

unsigned long previousMillis = 0;
const unsigned long INTERVAL = 60000; // 1 minutes in milliseconds (1 * 60 * 1000) = 60000, 300000 = 5min
int currentMinute = 0; // Simulated minute for timestamp

void setup() {
  Serial.begin(115200);
  
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  digitalWrite(trigPin, LOW);
  
  pinMode(trigPin2, OUTPUT);
  pinMode(echoPin2, INPUT);
  digitalWrite(trigPin2, LOW);
  
  pinMode(trigPin3, OUTPUT);
  pinMode(echoPin3, INPUT);
  digitalWrite(trigPin3, LOW);
}

void loop() {
  // Measure distances for all sensors
  digitalWrite(trigPin, HIGH);
  delay(1);
  digitalWrite(trigPin, LOW);
  Duration = pulseIn(echoPin, HIGH);
  Distance = Duration * 0.034 / 2; // Distance in cm

  digitalWrite(trigPin2, HIGH);
  delay(1);
  digitalWrite(trigPin2, LOW);
  Duration2 = pulseIn(echoPin2, HIGH);
  Distance2 = Duration2 * 0.034 / 2;

  digitalWrite(trigPin3, HIGH);
  delay(1);
  digitalWrite(trigPin3, LOW);
  Duration3 = pulseIn(echoPin3, HIGH);
  Distance3 = Duration3 * 0.034 / 2;

  // Update counts based on distance (50 cm threshold)
  if (Distance <= 50 && Distance > 5) {
    count++;
  } else {
    Distance = 0;
    count = 0;
  }

  if (Distance2 <= 50 && Distance2 > 5) {
    count2++;
  } else {
    Distance2 = 0;
    count2 = 0;
  }

  if (Distance3 <= 50 && Distance3 > 5) {
    count3++;
  } else {
    Distance3 = 0;
    count3 = 0;
  }

  //print the sensors data
  Serial.print("count: ");
  Serial.print(count);
  Serial.print(", count2: ");
  Serial.print(count2);
  Serial.print(", count3: ");
  Serial.print(count3);
  Serial.println();

  // Check if 1 minutes have passed
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= INTERVAL) {
    //Serial.println(currentMillis);
    sendDataToSerial();
    previousMillis = currentMillis;
  }

  delay(1000); // Check every second
}

void sendDataToSerial() {

  // Determine True/False based on counts > 30
  // True meaning for parking space is available, count>30 meaning the parking space is using and not available
  // True -> available, False -> not available
  String sensor1Status = (count >= 30) ? "False" : "True";
  String sensor2Status = (count2 >= 30) ? "False" : "True";
  String sensor3Status = (count3 >= 30) ? "False" : "True";

  String csvRow = "date," + sensor1Status + "," + sensor2Status + "," + sensor3Status;
  Serial.println();
  Serial.println("========================================================");
  Serial.println(csvRow);
  Serial.print("========================================================");
  Serial.println();
  
}