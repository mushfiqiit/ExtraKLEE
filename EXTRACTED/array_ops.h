

Status SetShapeFn(InferenceContext* c) {
      TF_RETURN_IF_ERROR(shape_inference::ValidateSparseTensor(
          c, c->input(0), c->input(1), c->input(2)));
      TF_RETURN_IF_ERROR(shape_inference::ValidateSparseTensor(
          c, c->input(3), c->input(4), c->input(5)));
      const Tensor* hypothesis_shape_t = c->input_tensor(2);
      const Tensor* truth_shape_t = c->input_tensor(5);
      if (hypothesis_shape_t == nullptr || truth_shape_t == nullptr) {
        // We need to know the runtime shape of the two tensors,
        // or else the output shape is unknown.
        return shape_inference::UnknownShape(c);
      }

      if (hypothesis_shape_t->NumElements() != truth_shape_t->NumElements()) {
        return errors::InvalidArgument(
            "Num elements of hypothesis_shape does not match truth_shape: ",
            hypothesis_shape_t->NumElements(), " vs. ",
            truth_shape_t->NumElements());
      }

      auto h_values = hypothesis_shape_t->flat<int64_t>();
      auto t_values = truth_shape_t->flat<int64_t>();
      std::vector<DimensionHandle> dims(hypothesis_shape_t->NumElements() - 1);
      for (int i = 0; i < dims.size(); ++i) {
        dims[i] = c->MakeDim(std::max(h_values(i), t_values(i)));
      }

      c->set_output(0, c->MakeShape(dims));
      return OkStatus();
    };