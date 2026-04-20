#!/bin/bash
# Get login page and extract CSRF token + cookie
RESPONSE=$(curl -sk -c /tmp/misp_jar.txt https://localhost/users/login)
TOKEN=$(echo "$RESPONSE" | grep -o 'data\[_Token\]\[key\]" value="[^"]*"' | grep -o 'value="[^"]*"' | cut -d'"' -f2)
FIELDS=$(echo "$RESPONSE" | grep -o 'data\[_Token\]\[fields\]" value="[^"]*"' | grep -o 'value="[^"]*"' | cut -d'"' -f2)

echo "Token: $TOKEN"
echo "Fields: $FIELDS"

# Submit login with same cookie jar
RESULT=$(curl -sk -c /tmp/misp_jar.txt -b /tmp/misp_jar.txt -X POST https://localhost/users/login \
  -d "_method=POST" \
  -d "data[_Token][key]=$TOKEN" \
  -d "data[User][email]=admin@misp.local" \
  -d "data[User][password]=LoveBella1000!" \
  -d "data[_Token][fields]=$FIELDS" \
  -d "data[_Token][unlocked]=" \
  -w "\nHTTP:%{http_code}" -L -o /tmp/misp_login_result.html 2>&1)

echo "Result: $RESULT"
echo "Page title: $(grep -o '<title>[^<]*</title>' /tmp/misp_login_result.html)"
