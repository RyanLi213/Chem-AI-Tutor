def predict_smiles_from_image(image_path: str) -> str:
    # Imported lazily: loading DECIMER pulls in TensorFlow and takes many seconds,
    # which shouldn't slow down anything that only needs the chemistry code.
    from DECIMER import predict_SMILES
    return predict_SMILES(image_path)
