def aggregate_ciphertexts(encrypted_vectors):
    """
    Performs homomorphic summation across N client encrypted vectors.
    Input: List of lists [ [c1_w1, c1_w2, ...], [c2_w1, c2_w2, ...] ]
    Output: Single list of encrypted sums [ c_sum_w1, c_sum_w2, ... ]
    """
    if not encrypted_vectors:
        raise ValueError("No encrypted vectors provided for aggregation.")
    
    num_weights = len(encrypted_vectors[0])
    num_clients = len(encrypted_vectors)
    
    aggregated_sum = []
    for weight_idx in range(num_weights):
        # Start with the first client's encrypted weight
        current_sum = encrypted_vectors[0][weight_idx]
        # Add remaining clients homomorphically
        for client_idx in range(1, num_clients):
            current_sum = current_sum + encrypted_vectors[client_idx][weight_idx]
        aggregated_sum.append(current_sum)
        
    return aggregated_sum