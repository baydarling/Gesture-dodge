
const uint8_t trigPin = 7;
const uint8_t echoPin = 8;

// Oyuncunun bulunabileceği şeritler
enum Serit {
    UST,
    ORTA,
    ALT
};

// Oyuncu başlangıçta orta şeritte
Serit aktifSerit = ORTA;

void setup() {
    Serial.begin(115200);

    pinMode(trigPin, OUTPUT);
    pinMode(echoPin, INPUT);
    digitalWrite(trigPin, LOW);
}

void loop() {

    // 1. Sensörü tetikle
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    // 2. Mesafeyi ölç
    unsigned long duration = pulseIn(echoPin, HIGH, 15000);

    if (duration == 0) {
        Serial.println("Olcum hatasi");
        delay(100);
        return;
    }

    float distance = duration * 0.0343 / 2.0;

    // Ölçüm aralığı dışındaysa şeridi değiştirme
    if (distance < 5 || distance > 35) {
        Serial.println("Gecersiz mesafe");
        delay(100);
        return;
    }

    // 3. HİSTEREZİS
    if (aktifSerit == UST) {
        if (distance >= 21) {
            aktifSerit = ALT;
        }
        else if (distance >= 13) {
            aktifSerit = ORTA;
        }
    }
    else if (aktifSerit == ORTA) {
        if (distance <= 11) {
            aktifSerit = UST;
        }
        else if (distance >= 21) {
            aktifSerit = ALT;
        }
    }
    else if (aktifSerit == ALT) {
        if (distance <= 11) {
            aktifSerit = UST;
        }
        else if (distance <= 19) {
            aktifSerit = ORTA;
        }
    }

    // 4. Sonucu yazdır
    Serial.print("Mesafe: ");
    Serial.print(distance);
    Serial.print(" cm | Serit: ");

    if (aktifSerit == UST) {
        Serial.println("UST");
    }
    else if (aktifSerit == ORTA) {
        Serial.println("ORTA");
    }
    else {
        Serial.println("ALT");
    }

    delay(100);
}
