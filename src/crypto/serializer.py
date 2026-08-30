import json
from phe import paillier

def serialize_payload(public_key, encrypted_vector):
    """Converts a Paillier public key and encrypted array into a JSON string."""
    payload = {
        'public_key': {'n': public_key.n},
        'values': [(str(x.ciphertext()), x.exponent) for x in encrypted_vector]
    }
    return json.dumps(payload)

def deserialize_payload(json_string):
    """Reconstructs the Paillier public key and encrypted array from JSON."""
    data = json.loads(json_string)
    
    pk_n = int(data['public_key']['n'])
    recovered_pk = paillier.PaillierPublicKey(n=pk_n)
    
    recovered_vector = [
        paillier.EncryptedNumber(recovered_pk, int(ct), int(exp))
        for ct, exp in data['values']
    ]
    
    return recovered_pk, recovered_vector