import utils
import sys
import json

n = int(sys.argv[1])
i = 2
iteration = 0
primes_list = []
while i ** 2 <= n:
    iteration += 1
    if n % i:
        i += 1
    else:
        n //= i
        primes_list.append(str(i))
primes_list.append(str(n))

sys.stdout.write(f'Result {json.dumps(primes_list)}')
